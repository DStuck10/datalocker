from django.conf.urls import patterns, url
from datalocker import views

urlpatterns = patterns('',
    url(r'^$', views.LockerListView.as_view(), name='index'),
    url(r'^(?P<locker_id>[0-9]+)/submissions$',
    	views.LockerSubmissionView.as_view(),
    	name='submissions_list'
    	),
    url(r'^(?P<locker_id>[0-9]+)/submissions/(?P<submission_id>[0-9]+)/view$',
    	views.SubmissionView.as_view(),
    	name='submission_view'
    	),
)

##
# EXAMPLE Urls
#
# /datalocker
# /datalocker/#/submissions
# /datalocker/#/submissions/#/view
# /datalocker/#/settings
# /datalocker/#/submissions/#/comments

