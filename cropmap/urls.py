from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^api/crops_in_circle$', 'browser.views.crops_in_circle'),
    url(r'^api/reload_data$', 'browser.views.reload_data'),
)
