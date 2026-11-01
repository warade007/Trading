from django.urls import path
from research.views import dashboard
from brokers import views as broker_views

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("accounts/login/", broker_views.AdministratorLoginView.as_view(), name="administrator_login"),
    path("accounts/logout/", broker_views.administrator_logout, name="administrator_logout"),
    path("settings/broker/", broker_views.broker_settings, name="broker_settings"),
    path("settings/broker/test/", broker_views.test_connection, name="broker_test"),
    path("settings/broker/login/", broker_views.login_zerodha, name="broker_login"),
    path("settings/broker/disconnect/", broker_views.disconnect_broker, name="broker_disconnect"),
    path("settings/broker/delete/", broker_views.delete_credentials, name="broker_delete"),
    path("kite/callback", broker_views.kite_callback, name="kite_callback"),
]
