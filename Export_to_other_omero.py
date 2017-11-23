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
from path import path
import os
import omero.cli
import omero.scripts as scripts
from omero.gateway import BlitzGateway


REMOTE_HOST = 'demo.openmicroscopy.org'
REMOTE_PORT = 4064

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
c = omero.client(host=REMOTE_HOST, port=REMOTE_PORT, args=["--Ice.Config=/dev/null"])
c.createSession(username, password)
try:
    # Just to test connection, print the projects.
    remote_conn = BlitzGateway(client_obj=c)
    for p in remote_conn.getObjects("Project"):
	    print p.id, p.name

    print "Connected to ", REMOTE_HOST, ", now to transfer image"
    cli = omero.cli.CLI()
    cli.loadplugins()
    cli.set_client(c)
    del os.environ["ICE_CONFIG"]

    # TODO Find location of ManagedRepository
    #TODO get selected file from user choice
    file_loc = "/Users/eilidhtroup/omero/ManagedRepository/root_0/2017-10/06/" \
               "16-21-46.945/antibiotic_plate.jpg"
    cli.invoke(["import", file_loc])

    # End of transferring image
finally:
    remote_conn.close()
    c.closeSession()

# Return some value(s).

# Here, we return anything useful the script has produced.
# NB: The Insight and web clients will display the "Message" output.

# msg = "Script ran with Image ID: %s, Name: %s and \nUsername: %s"\
#       % (image_id, image.getName(), username)
# client.setOutput("Message", rstring(msg))

client.closeSession()
