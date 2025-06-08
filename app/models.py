from fireo.fields import DateTime, TextField
from fireo.models import Model


class WebsiteContent(Model):
    """This model stores webpage content snapshots for each hour."""

    timestamp = DateTime(auto=True)
    url = TextField()
    content_snapshot = TextField()
    diff = TextField()
