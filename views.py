### Copyright 2015 The Pennsylvania State University. Office of the Vice Provost for Educational Equity. All Rights Reserved. ###

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.mail.message import EmailMessage
from django.core.urlresolvers import reverse
from django.db.models.query import QuerySet
from django.db.models import Max
from django.forms.models import model_to_dict
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, render_to_response, get_object_or_404
from django.template.loader import get_template
from django.template import Context
from django.utils import timezone
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import View

from .decorators import user_has_locker_access
from .models import Comment, Locker, LockerManager, LockerSetting, LockerQuerySet, Submission

import datetime, json, requests


##
## Helper Functions
##
def _get_public_user_dict(user):
    public_fields = ['id', 'email', 'first_name', 'last_name']
    user_dict = {}
    for key, value in model_to_dict(user).iteritems():
        if key in public_fields:
            user_dict[key] = value
    return user_dict



def _get_public_comment_dict(comment):
    public_fields = ['comment', 'submission', 'user', 'id', 'parent_comment']
    comment_dict = {}
    for key, value in model_to_dict(comment).iteritems():
        if key in public_fields:
            comment_dict[key] = value
            if key == 'user':
                name = User.objects.get(id=value).username
                username = ''.join([i for i in name if not i.isdigit()])
                comment_dict[key] = username
    return comment_dict




def add_comment(request, **kwargs):
    if request.method == 'POST':
        submission = get_object_or_404(Submission, id=kwargs['pk'])
        user_comment = request.POST.get('comment', '')
        comment = Comment(
            submission=submission,
            comment=user_comment,
            user=request.user,
            timestamp=timezone.now(),
            )
        comment.save()
        return JsonResponse({
            'comment': user_comment,
            'submission': submission.id,
            'user': request.user.username,
            'id': comment.id,
            })
    else:
        locker_id = kwargs['locker_id']
        pk = kwargs['pk']
        return HttpResponseRedirect(reverse('datalocker:submissions_view',
         kwargs={'locker_id': locker_id, 'pk': pk}))




def edit_comment(request, **kwargs):
    if request.method == 'POST':
        submission = get_object_or_404(Submission, id=kwargs['pk'])
        user_comment = request.POST.get('comment', '')
        comment = Comment.objects.get(
            id=request.POST.get('id'),
            )
        if Comment.is_editable(comment):
            comment.comment = user_comment
            comment.save()
        return JsonResponse({
            'comment': user_comment,
            'submission': submission.id,
            'user': request.user.username,
            'id': comment.id,
            })
    else:
        locker_id = kwargs['locker_id']
        pk = kwargs['pk']
        return HttpResponseRedirect(reverse('datalocker:submissions_view',
         kwargs={'locker_id': locker_id, 'pk': pk}))




def add_reply(request, **kwargs):
    if request.method == 'POST':
        submission = get_object_or_404(Submission, id=kwargs['pk'])
        parent_comment = get_object_or_404(Comment, id=request.POST['parent_comment'])
        user_comment = request.POST.get('comment', '')
        comment = Comment(
            submission=submission,
            comment=user_comment,
            user=request.user,
            timestamp=timezone.now(),
            parent_comment=parent_comment,
            )
        comment.save()
        return JsonResponse({
            'comment': user_comment,
            'submission': submission.id,
            'user': request.user.username,
            'id': comment.id,
            'parent_comment': parent_comment.id
            })
    else:
        locker_id = kwargs['locker_id']
        pk = kwargs['pk']
        return HttpResponseRedirect(reverse('datalocker:submissions_view',
         kwargs={'locker_id': locker_id, 'pk': pk}))




def archive_locker(request, **kwargs):
    locker = get_object_or_404(Locker, id=kwargs['locker_id'])
    owner = locker.owner
    locker.archive_timestamp = timezone.now()
    locker.save()
    if request.is_ajax():
        return JsonResponse({})
    else:
        return HttpResponseRedirect(reverse('datalocker:index'))




def custom_404(request):
    response = render_to_response('404.html')
    response.status_code = 404
    return response




def delete_submission(request, **kwargs):
    submission = get_object_or_404(Submission, id=kwargs['pk'])
    submission.deleted = timezone.now()
    submission.save()
    if request.is_ajax():
        return JsonResponse({
            'id': submission.id,
            'timestamp': submission.timestamp,
            })
    else:
        return HttpResponseRedirect(reverse('datalocker:submission_list',
            kwargs={'id': self.kwargs['id']}))




@csrf_exempt
@require_http_methods(["POST"])
def form_submission_view(request, **kwargs):
    """
    Handles form submissions from outside applications to be saved in lockers.
    """
    safe_values = {
        'identifier': request.POST.get('form-id', ''),
        'name': request.POST.get('name', 'New Locker'),
        'url': request.POST.get('url', ''),
        'owner': request.POST.get('owner', ''),
        'data': request.POST.get('data', ''),
        }
    locker, created = Locker.objects.get_or_create(
        form_identifier=safe_values['identifier'],
        archive_timestamp=None,
        defaults={
            'name': safe_values['name'],
            'form_url': safe_values['url'],
            'owner': safe_values['owner'],
            }
        )
    submission = Submission(
        locker = locker,
        data = safe_values['data'],
        )
    submission.save()

    try:
        address = User.objects.get(username=safe_values['owner']).email
    except User.DoesNotExist:
        """ TODO: do something about this as the locker's owner doesn't have
               an account so therefore likely won't be able to access it.
               Might have to alert an administrator so they can assign
               the locker to someone or create an account for the owner. """
        pass
    else:
        subject = "%s - new submission - Data Locker" % safe_values['name']
        message = "Data Locker: new form submission saved\n\n" \
            "Form: %s\n\n" \
            "View submission: %s\n" \
            "View all submissions: %s\n" % (
                request.POST.get('name', 'New Locker'),
                reverse(
                    'datalocker:submissions_view',
                    kwargs={'locker_id': locker.id, 'pk': submission.id}
                    ),
                reverse(
                    'datalocker:submissions_list',
                    kwargs={'locker_id': locker.id,}
                    ),
                )
        try:
            send_mail(subject, message, from_email, [address])
        except Exception, e:
            """ TODO: log the failure here """
            pass
    return HttpResponse(status=201)




class LoginRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)



class UserHasLockerAccessMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(UserHasLockerAccessMixin, cls).as_view(**initkwargs)
        return user_has_locker_access(view)




class LockerListView(LoginRequiredMixin, generic.ListView):
    template_name = 'datalocker/index.html'
    model = Locker


    def get_context_data(self, **kwargs):
        """
        Accesses the logged in user and searched through all the lockers they
        have access to. It only returns the lockers that they have access to
        and don't own.
        """
        user = self.request.user
        context = super(LockerListView, self).get_context_data(**kwargs)
        context['shared'] = Locker.objects.active().has_access(
            self.request.user).annotate(latest_submission= Max(
                'submissions__timestamp')).order_by('name').exclude(
                    owner=user)
        context['owned'] = Locker.objects.active().has_access(
            self.request.user).annotate(latest_submission= Max(
                'submissions__timestamp')).order_by('name').filter(
                    owner=user)
        return context




class LockerSubmissionsListView(LoginRequiredMixin, generic.ListView):
    template_name = 'datalocker/submission_list.html'


    def get_context_data(self, **kwargs):
        context = super(LockerSubmissionsListView, self).get_context_data(**kwargs)
        locker = Locker.objects.get(pk=self.kwargs['locker_id'])
        context['locker'] = locker
        fields_list = locker.get_all_fields_list()
        context['fields_list'] = fields_list
        selected_fields = locker.get_selected_fields_list()
        context['selected_fields'] = selected_fields
        context['column_headings'] = ['Submitted Date', ] + selected_fields
        context['data'] = []
        for submission in locker.submissions.all().order_by('-timestamp'):
            entry = [submission.id, True if submission.deleted else False, submission.timestamp, ]
            for field, value in submission.data_dict().iteritems():
                if field in selected_fields:
                    entry.append(value)
            context['data'].append(entry)
        return context


    def get_queryset(self):
        """ Return all submissions for selected locker """
        return Submission.objects.filter(
            locker_id=self.kwargs['locker_id']).order_by('-timestamp')


    def post(self, *args, **kwargs):
        """
        Takes the checkboxes selected on the select fields dialog and saves
        those as a selected-fields setting which is loaded then on every page
        load thereafter.
        """
        locker = Locker.objects.get(pk=self.kwargs['locker_id'])
        locker.save_selected_fields_list(self.request.POST)
        return HttpResponseRedirect(reverse('datalocker:submissions_list',
            kwargs={'locker_id': self.kwargs['locker_id']}))




def get_comments_view(request, **kwargs):
    locker = Locker.objects.get(id=kwargs['locker_id'])
    setting = LockerSetting.objects.get(locker=locker, category='discussion')
    if setting.value == u'True':
        if request.is_ajax():
            # If statement to make sure the user should be able to see the comments
            all_comments = Comment.objects.filter(submission=kwargs['pk'], parent_comment=None)
            all_replies = Comment.objects.filter(submission=kwargs['pk']
                ).exclude(parent_comment=None)
            comments = []
            replies = []
            for comment in all_comments:
                comments.append(_get_public_comment_dict(comment))
            for comment in all_replies:
                replies.append(_get_public_comment_dict(comment))
            return JsonResponse(
                {
                'comments': comments,
                'replies': replies
                })
        else:
            return HttpResponseRedirect(reverse('datalocker:submissions_view',
         kwargs={'locker_id': locker.id, 'pk': pk}))
    else:
        pk = Submission.objects.get(id=kwargs['pk'])
        return HttpResponseRedirect(reverse('datalocker:submissions_view',
         kwargs={'locker_id': locker.id, 'pk': pk}))




def locker_users(request, locker_id):
    if request.is_ajax():
        locker = get_object_or_404(Locker, pk=locker_id)
        users = []
        for user in locker.users.all():
            users.append(_get_public_user_dict(user))
        return JsonResponse({'users': users})
    else:
        return HttpResponseRedirect(reverse('datalocker:index'))




class LockerUserAdd(View):
    def post(self, *args, **kwargs):
        user = get_object_or_404(User, email=self.request.POST.get('email', ''))
        locker =  get_object_or_404(Locker, id=kwargs['locker_id'])
        if not user in locker.users.all():
            locker.users.add(user)
            locker.save()
        from_email = 'eeqsys@psu.edu'
        locker_name = Locker.objects.get(id=kwargs['locker_id'])
        subject = 'Granted Locker Access'
        to = self.request.POST.get('email', "")
        body = 'Hello, ' + to +'\n'+' You now have access to a locker ' +  locker_name.name
        email = EmailMessage(subject, body, from_email, [to])
        email.send()
        return JsonResponse(_get_public_user_dict(user))




class LockerUserDelete(View):
    def post(self , *args, **kwargs):
        user = get_object_or_404(User, id=self.request.POST.get('id', ''))
        locker =  get_object_or_404(Locker, id=kwargs['locker_id'])
        if user in locker.users.all():
            locker.users.remove(user)
            locker.save()
        return JsonResponse({'user_id': user.id})




class SubmissionView(LoginRequiredMixin, generic.DetailView):
    template_name = 'datalocker/submission_view.html'
    model = Submission


    def get_context_data(self, **kwargs):
        context = super(SubmissionView, self).get_context_data(**kwargs)
        context['oldest_disabled'] = True if self.object.id == self.object.oldest() else False
        context['older_disabled'] = True if self.object.id == self.object.older() else False
        context['newer_disabled'] = True if self.object.id == self.object.newer() else False
        context['newest_disabled'] = True if self.object.id == self.object.newest() else False
        context['sidebar_enabled'] = True
        context['commenting_enabled'] = True if LockerSetting.objects.get(locker=kwargs['object'].locker,
            category='discussion').value == u'True' else False
        return context




@require_http_methods(["POST"])
def modify_locker(request, **kwargs):
    locker =  get_object_or_404(Locker, id=kwargs['locker_id'])
    locker_name = locker.name
    locker_owner = locker.owner
    new_locker_name = request.POST.get('edit-locker', '')
    new_owner = request.POST.get('edit-owner', '')
    if new_locker_name != "":
        locker.name = new_locker_name
    if new_owner != "":
        try:
            user = User.objects.get(email=new_owner).username
        except User.DoesNotExist:
            ### TODO: Log this and deal with it
            pass
        else:
            locker.owner = user
    locker.save()
    return HttpResponseRedirect(reverse('datalocker:index'))




def unarchive_locker(request, **kwargs):
    locker = get_object_or_404(Locker, id=kwargs['locker_id'])
    owner = locker.owner
    locker.archive_timestamp = None
    locker.save()
    return HttpResponseRedirect(reverse('datalocker:index'))




def undelete_submission(request, **kwargs):
    submission = get_object_or_404(Submission, id=kwargs['pk'])
    submission.deleted = None
    submission.save()
    if request.is_ajax():
        return JsonResponse({
            'id': submission.id,
            'timestamp': submission.timestamp,
            })
    else:
        return HttpResponseRedirect(reverse('datalocker:submission_list'))