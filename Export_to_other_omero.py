#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Adapted from https://github.com/openmicroscopy/openmicroscopy/blob/develop/
# examples/Training/python/Scripting_Service_Example.py
#

# This script takes an Image ID, a username and a password as parameters from
# the scripting service.
import omero
from omero.rtypes import rlong, rstring, unwrap
from omero.gateway import BlitzGateway
import omero.scripts as scripts
import omero.fs
from path import path
import sys
import subprocess

# Script definition

# Script name, description and 2 parameters are defined here.
# These parameters will be recognised by the Insight and web clients and
# populated with the currently selected Image(s)
# A username and password will be entered too.

# this script only takes Images (not Datasets etc.)
data_types = [rstring('Image')]
client = scripts.client(
    "Export_to_other_omero.py",
    ("Script to export a file to another omero server."),
    # first parameter
    scripts.String(
        "Data_Type", optional=False, values=data_types, default="Image",
        grouping="1.1"),
    # second parameter
    scripts.List("IDs", optional=False, grouping="1.2").ofType(rlong(0)),
    # username
    scripts.String("username", optional=False, grouping="2.1"),
    # password
    scripts.String("password", optional=False, grouping="2.2")
)
# we can now create our local Blitz Gateway by wrapping the client object
local_conn = BlitzGateway(client_obj=client)

# get the 'IDs' parameter (which we have restricted to 'Image' IDs)
ids = unwrap(client.getInput("IDs"))
image_id = ids[0]        # simply use the first ID for this example
username = client.getInput("username", unwrap=True)
password = client.getInput("password", unwrap=True)

# Find image files
image = local_conn.getObject("Image", image_id)
print image.getName()
for f in image.getImportedImageFiles():
   print f.path,f.name

# Connect to remote omero
remote_host = 'demo.openmicroscopy.org'
remote_port = 4064

c = omero.client(host=remote_host, port=remote_port, args=["--Ice.Config=/dev/null"])
c.createSession(username, password)
try:
    remote_conn = BlitzGateway(client_obj=c)
    for p in remote_conn.getObjects("Project"):
	    print p.id, p.name


    # Transfer image over
    key = c.getSessionId()

    args = [sys.executable]
    args.append(str(path(".") / "bin" / "omero"))
    args.extend(
        ["-s", remote_host, "-k", key, "-p", str(remote_port), "import"])

    # TODO Find location of ManagedRepository
    #TODO get selected file from user choice

    file_loc = "/Users/eilidhtroup/omero/ManagedRepository/root_0/2017-10/06/" \
               "16-21-46.945/antibiotic_plate.jpg"
    # file_loc = "root_0/2017-10/06/" \
    #            "16-21-46.945/antibiotic_plate.jpg"
    args.append(file_loc)

    print "args are"
    print args

    # TODO could get omero_dist as done in def omerodistdir(cls):
    # from https://github.com/openmicroscopy/openmicroscopy/blob/develop/components/tools/OmeroPy/src/omero/testlib/__init__.py#L277
    popen = subprocess.Popen(args,  # cwd=str(self.omero_dist),
                             cwd="/Users/eilidhtroup/Documents/SynthSysDataManagement/omero/omeroServer/OMERO.server",
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    out, err = popen.communicate()
    rc = popen.wait()
    if rc != 0:
        raise Exception("import failed: [%r] %s\n%s" % (args, rc, err))
    pix_ids = []
    print "Output"
    for x in out.split("\n"):
        print x
        if x and x.find("Created") < 0 and x.find("#") < 0:
            try:  # if the line has an image ID...
                image_id = str(long(x.strip()))
                # Occasionally during tests an id is duplicated on stdout
                if image_id not in pix_ids:
                    pix_ids.append(image_id)
            except:
                pass

    print "pix_ids"
    print pix_ids
    # End of transferring image
finally:
    c.closeSession()
   # remote_conn.close()
# Return some value(s).

# Here, we return anything useful the script has produced.
# NB: The Insight and web clients will display the "Message" output.

msg = "Script ran with Image ID: %s, Name: %s and \nUsername: %s"\
      % (image_id, image.getName(), username)
client.setOutput("Message", rstring(msg))

client.closeSession()
