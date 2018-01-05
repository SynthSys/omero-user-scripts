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
import sys
from tempfile import NamedTemporaryFile
from contextlib import contextmanager
import re
import keyring

# old_stdout = sys.stdout
# temp_file = NamedTemporaryFile(delete=False)
# sys.stdout = temp_file

REMOTE_HOST = 'demo.openmicroscopy.org'
REMOTE_PORT = 4064

# A couple of helper methods for capturing sys.stdout
#

# From stackoverflow https://stackoverflow.com/questions/4675728/redirect-stdout
# -to-a-file-in-python/22434262#22434262

def fileno(file_or_fd):
    print "file_or_fd is: ", file_or_fd
    # file_or_fd.fileno()
    fd = getattr(file_or_fd, 'fileno', lambda: file_or_fd)()
    if not isinstance(fd, int):
        raise ValueError("Expected a file (`.fileno()`) or a file descriptor")
    return fd

@contextmanager
def stdout_redirected(to=os.devnull, stdout=None):
    if stdout is None:
       stdout = sys.stdout

    stdout_fd = fileno(stdout)
    print "stdout_fd is: ", stdout_fd
    # copy stdout_fd before it is overwritten
    #NOTE: `copied` is inheritable on Windows when duplicating a standard stream
    with os.fdopen(os.dup(stdout_fd), 'wb') as copied:
        stdout.flush()  # flush library buffers that dup2 knows nothing about
        try:
            os.dup2(fileno(to), stdout_fd)  # $ exec >&to
        except ValueError:  # filename
            with open(to, 'wb') as to_file:
                os.dup2(to_file.fileno(), stdout_fd)  # $ exec > to
        try:
            yield stdout # allow code to be run with the redirected stdout
        finally:
            # restore stdout to its previous value
            #NOTE: dup2 makes stdout_fd inheritable unconditionally
            stdout.flush()
            os.dup2(copied.fileno(), stdout_fd)  # $ exec >&copied

# End helper methods for capturing sys.stdout


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
    scripts.String("username", optional=False, grouping="2.1")#,
    # password
    # scripts.String("password", optional=False, grouping="2.2")
)
# we can now create our local Blitz Gateway by wrapping the client object
local_conn = BlitzGateway(client_obj=client)

# get the 'IDs' parameter (which we have restricted to 'Image' IDs)
ids = unwrap(client.getInput("IDs"))

username = client.getInput("username", unwrap=True)
#password = client.getInput("password", unwrap=True)
password = keyring.get_password("omero", username)
# The managed_dir is where the local images are stored.
managed_dir = client.sf.getConfigService().getConfigValue("omero.managed.dir")

# Connect to remote omero
c = omero.client(host=REMOTE_HOST, port=REMOTE_PORT,
                 args=["--Ice.Config=/dev/null", "--omero.debug=1"])
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

    # Find image files
    uploaded_image_ids = []
    for image_id in ids:
        image = local_conn.getObject("Image", image_id)
        print image.getName()

        temp_file = NamedTemporaryFile().name
        try:
            # TODO haven't tested an image with multiple files.
            for f in image.getImportedImageFiles():
                file_loc = os.path.join(managed_dir, f.path, f.name)
                print "file location is: ", file_loc
                with open(temp_file, 'wr') as f, stdout_redirected(f):
                    cli.invoke(["import", file_loc])

                with open(temp_file, 'r') as f:
                    txt = f.readline()
                    print "text is ", txt
                    assert txt.startswith("Image:")
                    uploaded_image_ids.append(re.findall(r'\d+', txt)[0])

            print "ids are: ", uploaded_image_ids
        # See this for how to scrape image id from file:
        # https://github.com/openmicroscopy/openmicroscopy/blob/develop/components/
        # tools/OmeroPy/src/omero/testlib/__init__.py#L277
        except Exception as inst:
            # TODO handle errors.
            print type(inst)  # the exception instance
            print inst.args  # arguments stored in .args
            print inst
        finally:
            pass

    print "uploaded image ids: ", uploaded_image_ids
        # End of transferring image
finally:
    print
    remote_conn.close()
    c.closeSession()


# Return some value(s).

# Here, we return anything useful the script has produced.
# NB: The Insight and web clients will display the "Message" output.

# msg = "Script ran with Image ID: %s, Name: %s and \nUsername: %s"\
#       % (image_id, image.getName(), username)
# client.setOutput("Message", rstring(msg))

client.closeSession()