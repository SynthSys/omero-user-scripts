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
remote_conn = BlitzGateway(client_obj=c)
for p in remote_conn.getObjects("Project"):
	print p.id, p.name


remote_conn.close()
# Return some value(s).

# Here, we return anything useful the script has produced.
# NB: The Insight and web clients will display the "Message" output.

msg = "Script ran with Image ID: %s, Name: %s and \nUsername: %s"\
      % (image_id, image.getName(), username)
client.setOutput("Message", rstring(msg))

client.closeSession()
