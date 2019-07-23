from django.views import generic
from django.views.generic.edit import FormView, UpdateView
from django.shortcuts import render, redirect, reverse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from .models import OffChallenge
from .forms import ChallengeRequestForm, ChallengeConfirmationForm

# Candidate portal home
@method_decorator(login_required(login_url='/accounts/login/'), name='dispatch')
class IndexView(generic.TemplateView):
    template_name = 'candidate/index.html'
    context_object_name = 'my_favorite_publishers'

    def get_context_data(self):
        challenges = OffChallenge.objects \
                .order_by('-request_date') \
                .filter(requester__exact=self.request.user)
        reviewed_challenges = challenges.filter(reviewed=True)
        context = {
            'num_pending' : challenges.filter(reviewed=False).count(),
            'num_rejected' : reviewed_challenges.filter(confirmed=False).count(),
            'num_confirmed' : reviewed_challenges.filter(confirmed=True).count()
        }
        return context


# Form for submitting officer challenge requests
# And list of past requests for candidate
@method_decorator(login_required(login_url='/accounts/login/'), name='dispatch')
class CandRequestView(FormView, generic.ListView):
    template_name = 'candidate/candreq.html'
    form_class = ChallengeRequestForm
    success_url = "/cand/candreq"

    context_object_name = 'challenge_list'

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        form.instance.requester = self.request.user
        form.save()
        self.send_email(form)
        return super().form_valid(form)

    def send_email(self, form):
        subject = 'Confirm Officer Challenge'
        officer_email = form.instance.officer.email
        text_content = 'Confirm officer challenge'

        candidate_name = form.instance.requester.get_full_name()
        candidate_username = form.instance.requester.username
        link = self.request.build_absolute_uri(
                reverse("candidate:challengeconfirm", kwargs={ 'pk' : form.instance.id }))
        html_content = render_to_string(
            'candidate/email.html',
            {
                'pk': form.instance.id,
                'candidate_name' : candidate_name,
                'candidate_username' : candidate_username,
                'link' : link,
            }
        )
        msg = EmailMultiAlternatives(subject, text_content,
                'no-reply@hkn.eecs.berkeley.edu', [officer_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()

    def get_queryset(self):
        result = OffChallenge.objects \
                .order_by('-request_date') \
                .filter(requester__exact=self.request.user)
        return result


# List of past challenge requests for officer
# Non-officers can still visit this page but will not have any entries
@method_decorator(login_required(login_url='/accounts/login/'), name='dispatch')
class OffRequestView(generic.ListView):
    template_name = 'candidate/offreq.html'

    context_object_name = 'challenge_list'

    def get_queryset(self):
        result = OffChallenge.objects \
                .order_by('-request_date') \
                .filter(officer__exact=self.request.user)
        return result


# Officer views and confirms a challenge request after clicking email link
# Only the officer who game the challenge can review it
@login_required(login_url='/accounts/login/')
def officer_confirm_view(request, pk):
    challenge = OffChallenge.objects.get(id=pk)
    if request.user.id != challenge.officer.id:
        return render(request, "candidate/401.html", status=401)

    requester_name = challenge.requester.get_full_name()
    form = ChallengeConfirmationForm(request.POST or None, instance=challenge)
    context = {
        'challenge' : challenge,
        'requester_name' : requester_name,
        'form': form,
    }

    if form.is_valid():
        form.instance.reviewed = True
        form.save()
        return redirect('/cand/reviewconfirm/' + pk)
    return render(request, "candidate/challenge_confirm.html", context=context)


# The page displayed after officer reviews challenge and clicks "submit"
def officer_review_confirmation(request, pk):
    challenge = OffChallenge.objects.get(id=pk)
    requester_name = challenge.requester.get_full_name()
    context = {
        'challenge' : challenge,
        'requester_name' : requester_name,
    }
    return render(request, "candidate/review_confirm.html", context=context)


# Detail view of an officer challenge
@login_required(login_url='/accounts/login/')
def challenge_detail_view(request, pk):
    challenge = OffChallenge.objects.get(id=pk)
    officer_name = challenge.officer.get_full_name()
    requester_name = challenge.requester.get_full_name()
    # check whether the view of page is the officer who gave the challenge
    viewer_is_officer = challenge.officer == request.user
    if viewer_is_officer:
        review_link = request.build_absolute_uri(
                reverse("candidate:challengeconfirm", kwargs={ 'pk' : pk }))
    else:
        review_link = None
    context = {
        "challenge" : challenge,
        "officer_name" : officer_name,
        "requester_name" : requester_name,
        "viewer_is_officer" : viewer_is_officer,
        "review_link" : review_link,
    }
    return render(request, "candidate/challenge_detail.html", context=context)
