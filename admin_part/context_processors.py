from .models import SiteSetting, TeamMember


def site_settings_context(request):
    site_settings = SiteSetting.objects.first()
    team_members = TeamMember.objects.all()
    return {
        'site_settings': site_settings or {},
        'team_members': team_members,
    }
