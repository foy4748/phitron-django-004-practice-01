from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http.response import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse
from django.views.generic import CreateView, ListView
from accounts.models import UserBankAccount
from core.models import SiteCustomConfigs
from transactions.constants import DEPOSIT, TRANSFER, WITHDRAWAL, LOAN, LOAN_PAID
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from datetime import datetime
from django.db.models import Sum
from transactions.forms import (
    DepositForm,
    TransferForm,
    WithdrawForm,
    LoanRequestForm,
)
from transactions.models import Transaction


isSendEmail = False


def send_transaction_email(user, amount, subject, template):
    message = render_to_string(
        template,
        {
            "user": user,
            "amount": amount,
        },
    )
    send_email = EmailMultiAlternatives(subject, "", to=[user.email])
    send_email.attach_alternative(message, "text/html")
    send_email.send()


class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = "transactions/transaction_form.html"
    model = Transaction
    title = ""
    success_url = reverse_lazy("transaction_report")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"account": self.request.user.account})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(
            **kwargs
        )  # template e context data pass kora
        context.update({"title": self.title})

        return context


class DepositMoneyView(TransactionCreateMixin):
    form_class = DepositForm
    title = "Deposit"

    def get_initial(self):
        initial = {"transaction_type": DEPOSIT}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get("amount")
        account = self.request.user.account
        # if not account.initial_deposit_date:
        #     now = timezone.now()
        #     account.initial_deposit_date = now
        account.balance += (
            amount  # amount = 200, tar ager balance = 0 taka new balance = 0+200 = 200
        )
        account.save(update_fields=["balance"])

        messages.success(
            self.request,
            f'{"{:,.2f}".format(float(amount))}$ was deposited to your account successfully',
        )
        if isSendEmail is True:
            send_transaction_email(
                self.request.user,
                amount,
                "Deposite Message",
                "transactions/deposite_email.html",
            )
        return super().form_valid(form)


class WithdrawMoneyView(TransactionCreateMixin):
    form_class = WithdrawForm
    title = "Withdraw Money"

    def dispatch(self, request, *args, **kwargs):
        d = super().dispatch(request, *args, **kwargs)
        site_custom_settings = SiteCustomConfigs.objects.all().first()
        if site_custom_settings.is_bankrupt is True:
            return HttpResponse("Bank is bankrupt".encode("utf-8"))
        return d

    def get_initial(self):
        initial = {"transaction_type": WITHDRAWAL}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get("amount")

        self.request.user.account.balance -= form.cleaned_data.get("amount")
        # balance = 300
        # amount = 5000
        self.request.user.account.save(update_fields=["balance"])

        messages.success(
            self.request,
            f'Successfully withdrawn {"{:,.2f}".format(float(amount))}$ from your account',
        )
        if isSendEmail is True:
            send_transaction_email(
                self.request.user,
                amount,
                "Withdrawal Message",
                "transactions/withdrawal_email.html",
            )
        return super().form_valid(form)


class LoanRequestView(TransactionCreateMixin):
    form_class = LoanRequestForm
    title = "Request For Loan"

    def get_initial(self):
        initial = {"transaction_type": LOAN}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get("amount")
        current_loan_count = Transaction.objects.filter(
            account=self.request.user.account, transaction_type=3, loan_approve=True
        ).count()
        if current_loan_count >= 3:
            # return HttpResponse("You have cross the loan limits")
            # Changed after Editor Error
            return HttpResponseRedirect("You have cross the loan limits")
        messages.success(
            self.request,
            f'Loan request for {"{:,.2f}".format(float(amount))}$ submitted successfully',
        )
        if isSendEmail is True:
            send_transaction_email(
                self.request.user,
                amount,
                "Loan Request Message",
                "transactions/loan_email.html",
            )
        return super().form_valid(form)


class TranserFormView(TransactionCreateMixin):
    form_class = TransferForm
    title = "Transfer"
    template_name = "transactions/transfer_form.html"

    def get_initial(self):
        initial = {"transaction_type": TRANSFER}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get("amount")
        account = self.request.user.account
        reciever_account_no = self.request.POST.get("reciever_account_no")
        print("Reciever account", reciever_account_no)
        reciever = None
        try:
            reciever = UserBankAccount.objects.get(account_no=reciever_account_no)
        except:
            return HttpResponse("Reciever Doesn't Exists")

        if reciever is None:
            return HttpResponseRedirect("Reciever Doesn't Exists")

        account.balance -= amount
        reciever.balance += amount
        account.save()
        reciever.save()

        messages.success(
            self.request,
            f'Transferred {"{:,.2f}".format(float(amount))}$ successfully',
        )

        if isSendEmail is True:
            send_transaction_email(
                self.request.user,
                amount,
                f"Transferred Balance to {reciever.user.username}",
                "transactions/transfer_email.html",
            )
            send_transaction_email(
                reciever.user,
                amount,
                f"Received Balance from {self.request.user.username}",
                "transactions/transfer_email.html",
            )
        return super().form_valid(form)


class TransactionReportView(LoginRequiredMixin, ListView):
    template_name = "transactions/transaction_report.html"
    model = Transaction
    balance = 0  # filter korar pore ba age amar total balance ke show korbe

    def get_queryset(self):
        queryset = super().get_queryset().filter(account=self.request.user.account)
        start_date_str = self.request.GET.get("start_date")
        end_date_str = self.request.GET.get("end_date")

        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

            queryset = queryset.filter(
                timestamp__date__gte=start_date, timestamp__date__lte=end_date
            )
            self.balance = Transaction.objects.filter(
                timestamp__date__gte=start_date, timestamp__date__lte=end_date
            ).aggregate(Sum("amount"))["amount__sum"]
        else:
            self.balance = self.request.user.account.balance

        return queryset.distinct()  # unique queryset hote hobe

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"account": self.request.user.account})

        return context


class PayLoanView(LoginRequiredMixin, View):
    def get(self, request, loan_id):
        loan = get_object_or_404(Transaction, id=loan_id)
        print(loan)
        if loan.loan_approve:
            user_account = loan.account
            # Reduce the loan amount from the user's balance
            # 5000, 500 + 5000 = 5500
            # balance = 3000, loan = 5000
            if loan.amount < user_account.balance:
                user_account.balance -= loan.amount
                loan.balance_after_transaction = user_account.balance
                user_account.save()
                loan.loan_approved = True
                loan.transaction_type = LOAN_PAID
                loan.save()
                return redirect("transactions:loan_list")
            else:
                messages.error(
                    self.request, f"Loan amount is greater than available balance"
                )

        return redirect("loan_list")


class LoanListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "transactions/loan_request.html"
    context_object_name = "loans"  # loan list ta ei loans context er moddhe thakbe

    def get_queryset(self):
        user_account = self.request.user.account
        queryset = Transaction.objects.filter(account=user_account, transaction_type=3)
        print(queryset)
        return queryset
