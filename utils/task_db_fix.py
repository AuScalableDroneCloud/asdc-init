"""
Issue:
    Queries are slow for users with many projects and tasks
    https://github.com/AuScalableDroneCloud/Tracker/issues/28

Hypothesis: console_output field is too large and causes this issue
Experiment: clear the console output data and compare timings of a query, original data backed up to a file
Prodedure:
- run on dev site first on a single user
- proven?
- run on prod site with a single problem user
- run on prod site for all users

"""

#When TESTMODE set, will just run the query and return for timing
TESTMODE = True
#TESTMODE = False

import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webodm.settings")
application = get_wsgi_application()

from app.models import Project, Task
from django.db import models
from django.contrib.auth.models import User

#print([f.name for f in Task._meta.get_fields()])

email = None
#Filtered by user
#email = "myname@domain.com"
if email is not None:
    user = User.objects.get(email = email)
    print(user)
    projects = Project.objects.filter(owner_id = user.id)
else:
    #All projects/tasks
    projects = Project.objects.all()

#print(projects)
for p in projects:
    print("PROJECT:", p.id)
    #status > 20 - not running or queued
    tasks = Task.objects.filter(project_id = p).filter(status__gt = 20) #.order_by('-created_at')
    for t in tasks:
        s = len(t.console_output)
        print(" - TASK:", t.id, s)
        if TESTMODE:
            continue

        if s < 10:
            print("    Skipping, console output length < 10 : {s}...")
            continue

        #Save the console output as a text file
        path = f"/webodm/app/media/project/{p.id}/task/{t.id}"
        if os.path.exists(path):
            fpath = f"{path}/console_output.txt"
            if not os.path.exists(fpath):
                with open(fpath, "w") as f:
                    f.write(t.console_output)
            else:
                print("    Skipping {fpath}, already exists...")
        else:
            print("    Skipping {path}, doesn't exist...")

        #Clear the field data
        t.console_output = ''
        t.save(update_fields=['console_output']) #Save only this field
        print("    Console output field cleared and saved.")

