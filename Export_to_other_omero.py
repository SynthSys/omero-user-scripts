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
import omero.util.script_utils as script_utils
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
TARGET_FLAG = '-T'

# A couple of helper methods for capturing sys.stdout
#

# From stackoverflow https://stackoverflow.com/questions/4675728/redirect-stdout
# -to-a-file-in-python/22434262#22434262


def fileno(file_or_fd):
    fd = getattr(file_or_fd, 'fileno', lambda: file_or_fd)()
    if not isinstance(fd, int):
        raise ValueError("Expected a file (`.fileno()`) or a file descriptor")
    return fd


@contextmanager
def stdout_redirected(to=os.devnull, stdout=None):
    if stdout is None:
        stdout = sys.stdout

    stdout_fd = fileno(stdout)
    # copy stdout_fd before it is overwritten
    # NOTE: `copied`is inheritable on Windows when duplicating a standard stream
    with os.fdopen(os.dup(stdout_fd), 'wb') as copied:
        stdout.flush()  # flush library buffers that dup2 knows nothing about
        try:
            os.dup2(fileno(to), stdout_fd)  # $ exec >&to
        except ValueError:  # filename
            with open(to, 'wb') as to_file:
                os.dup2(to_file.fileno(), stdout_fd)  # $ exec > to
        try:
            yield stdout  # allow code to be run with the redirected stdout
        finally:
            # restore stdout to its previous value
            # NOTE: dup2 makes stdout_fd inheritable unconditionally
            stdout.flush()
            os.dup2(copied.fileno(), stdout_fd)  # $ exec >&copied


# End helper methods for capturing sys.stdout
def run_script():
    # Script definition
    # Script name, description and 2 parameters are defined here.
    # These parameters will be recognised by the Insight and web clients and
    # populated with the currently selected Image(s)
    # A username and password will be entered too.
    # this script takes Images or Datasets
    message = ""
    data_types = [rstring('Dataset'), rstring('Image')]
    client = scripts.client(
        "Export_to_other_omero.py",
        "Script to export a file to another omero server.",
        scripts.String(
            "Data_Type", optional=False, values=data_types, default="Image",
            description="The data you want to work with.", grouping="1.1"),
        scripts.List("IDs", optional=False, grouping="1.2",
                     description="List of Dataset IDs or Image IDs").ofType(
            rlong(0)),
        # username
        scripts.String("username", optional=False, grouping="2.1")  # ,
        # password - getting from keyring, just for testing.
        # scripts.String("password", optional=False, grouping="2.2")
    )
    try:
        # we can now create our local Blitz Gateway by wrapping the client.
        local_conn = BlitzGateway(client_obj=client)
        script_params = client.getInputs(unwrap=True)

        message = copy_to_remote_omero(client, local_conn, script_params)
    finally:
        client.setOutput("Message: ", rstring(message))

    # Return some value(s).
    # Here, we return anything useful the script has produced.
    # NB: The Insight and web clients will display the "Message" output.
    # msg = "Script ran with Image ID: %s, Name: %s and \nUsername: %s"\
    #       % (image_id, image.getName(), username)
    # client.setOutput("Message", rstring(msg))
        client.closeSession()


def copy_to_remote_omero(client, local_conn, script_params):
    # TODO could maybe refactor to remove client
    data_type = script_params["Data_Type"]
    username = script_params["username"]
    # password = client.getInput("password", unwrap=True)
    password = keyring.get_password("omero", username)
    # The managed_dir is where the local images are stored.
    # TODO could pass this in instead of client?
    managed_dir = client.sf.getConfigService().getConfigValue(
        "omero.managed.dir")
    # # Get the images or datasets
    message = ""
    objects, log_message = script_utils.get_objects(local_conn, script_params)
    message += log_message
    if not objects:
        return message

    try:
        # Connect to remote omero
        c, cli = connect_to_remote(password, username)

        target_dataset = None
        uploaded_image_ids = []

        if data_type == 'Dataset':
            images = []
            # Refactor to do all of this for each dataset - for now, works for
            # one dataset.
            for ds in objects:
                dataset_name = ds.getName()
                target_dataset = "Dataset:name:" + dataset_name
                images.extend(list(ds.listChildren()))
                print("Processing {} images, in dataset {}".format(
                    len(images), dataset_name))
                for image in images:
                    uploaded_image_ids += upload_image(cli, image, managed_dir,
                                                       target_dataset)
            if not images:
                message += "No image found in dataset(s)"
                return message
        else:
            images = objects
            print("Processing %s images" % len(images))
            for image in images:
                uploaded_image_ids += upload_image(cli, image, managed_dir,
                                                   target_dataset)
    finally:
        c.closeSession()
        cli.close()
    # End of transferring images

    message += "uploaded image ids: " + str(tuple(uploaded_image_ids))
    print message
    return message


def connect_to_remote(password, username):
    c = omero.client(host=REMOTE_HOST, port=REMOTE_PORT,
                     args=["--Ice.Config=/dev/null", "--omero.debug=1"])
    c.createSession(username, password)
    # # Just to test connection, print the projects.
    # remote_conn = BlitzGateway(client_obj=c)
    # for p in remote_conn.getObjects("Project"):
    #     print p.id, p.name
    # print "Connected to ", REMOTE_HOST, ", now to transfer image"
    cli = omero.cli.CLI()
    cli.loadplugins()
    cli.set_client(c)
    del os.environ["ICE_CONFIG"]
    return c, cli


def upload_image(cli, image, managed_dir, target_dataset):

    print("Processing image: ID %s: %s" % (image.id, image.getName()))
    uploaded_image_ids = []
    temp_file = NamedTemporaryFile().name
    # TODO haven't tested an image with multiple files -see fileset.
    for f in image.getImportedImageFiles():
        file_loc = os.path.join(managed_dir, f.path, f.name)
        print "file location is: ", file_loc
        # This temp_file is a work around to get hold of the id of uploaded
        # images from stdout.
        with open(temp_file, 'wr') as tf, stdout_redirected(tf):
            if target_dataset:
                cli.onecmd(["import", file_loc, TARGET_FLAG, target_dataset])
            else:
                cli.onecmd(["import", file_loc])

        with open(temp_file, 'r') as tf:
            txt = tf.readline()
            # assert txt.startswith("Image:")
            uploaded_image_ids.append(re.findall(r'\d+', txt)[0])

    print "ids are: ", uploaded_image_ids
    return uploaded_image_ids


if __name__ == "__main__":
    run_script()
