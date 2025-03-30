import os
from .__init__ import create_app


app = create_app()
app.app_context().push()

