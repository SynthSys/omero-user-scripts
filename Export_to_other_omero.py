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
        local_conn.close()


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
        c, cli, remote_conn = connect_to_remote(password, username)

        images = []
        if data_type == 'Dataset':
            # TODO handle multiple datasets
            for ds in objects:
                dataset_name = ds.getName()
                target_dataset = "Dataset:name:" + dataset_name
                # create new remote dataset
                remote_ds = upload_dataset(cli, ds, remote_conn)

                images.extend(list(ds.listChildren()))
                if not images:
                    message += "No image found in dataset {}".format(
                        dataset_name)
                    return message

                print("Processing {} images, in dataset {}".format(
                    len(images), dataset_name))
                # TODO use remote_ds id, instead of target ds name
                uploaded_image_ids = upload_images(cli, images, managed_dir,
                                                   target_dataset, remote_conn)
        else:
            images = objects

            print("Processing %s images" % len(images))
            uploaded_image_ids = upload_images(cli, images, managed_dir,
                                               None, remote_conn)
    finally:
        close_remote_connection(c, cli, remote_conn)
    # End of transferring images

    message += "uploaded image ids: " + str(tuple(uploaded_image_ids))
    print message
    return message


def connect_to_remote(password, username):
    c = omero.client(host=REMOTE_HOST, port=REMOTE_PORT,
                     args=["--Ice.Config=/dev/null", "--omero.debug=1"])
    c.createSession(username, password)
    remote_conn = BlitzGateway(client_obj=c)
    cli = omero.cli.CLI()
    cli.loadplugins()
    cli.set_client(c)
    del os.environ["ICE_CONFIG"]
    return c, cli, remote_conn


def close_remote_connection(c, cli, remote_conn):
    remote_conn.close()
    c.closeSession()
    cli.close()


def upload_dataset(cli, ds, remote_conn):
    temp_file = NamedTemporaryFile().name
    # This temp_file is a work around to get hold of the id of uploaded
    # datasets from stdout.

    name_cmd = 'name=' + ds.getName()
    desc_cmd = "description="+ ds.getDescription()
    with open(temp_file, 'wr') as tf, stdout_redirected(tf):
            # bin/omero obj new Dataset name='new_dataset'
            cli.onecmd(["obj", "new", "Dataset", name_cmd, desc_cmd])

    with open(temp_file, 'r') as tf:
        txt = tf.readline()
        uploaded_dataset_id = re.findall(r'\d+', txt)[0]
    print "uploaded dataset ", uploaded_dataset_id
    remote_ds = remote_conn.getObject("Dataset", uploaded_dataset_id)
    # TODO add description and tags for dataset
    add_attachments(ds, remote_ds, remote_conn)
    return uploaded_dataset_id


def upload_images(cli, images, managed_dir, target_dataset,remote_conn):
    uploaded_image_ids = []
    uploaded_image_id = '';
    for image in images:
        print("Processing image: ID %s: %s" % (image.id, image.getName()))
        desc = image.getDescription()
        print "Description: ", desc
        temp_file = NamedTemporaryFile().name
        # TODO haven't tested an image with multiple files -see fileset.
        for f in image.getImportedImageFiles():
            file_loc = os.path.join(managed_dir, f.path, f.name)
            # This temp_file is a work around to get hold of the id of uploaded
            # images from stdout.
            with open(temp_file, 'wr') as tf, stdout_redirected(tf):
                if target_dataset:
                    cli.onecmd(["import", file_loc, '-T', target_dataset,
                                '--description', desc])
                else:
                    cli.onecmd(["import", file_loc, '--description', desc])

            with open(temp_file, 'r') as tf:
                txt = tf.readline()
                # assert txt.startswith("Image:")
                uploaded_image_id = re.findall(r'\d+', txt)[0]
        uploaded_image_ids.append(uploaded_image_id)

        # TODO check what happens when an image has multiple files.
        remote_image = remote_conn.getObject("Image", uploaded_image_id)
        add_attachments(image, remote_image, remote_conn)

    print "ids are: ", uploaded_image_ids
    return uploaded_image_ids


def add_attachments(local_item, remote_item, remote_conn):
    # Sometimes the image already has the tags uploaded.
    # Finding these so we can check for duplications.
    pre_loaded_tags = []
    for existing_ann in remote_item.listAnnotations():
        if existing_ann.OMERO_TYPE == omero.model.TagAnnotationI:
            print "Tag is already there: ", existing_ann.getTextValue()
            pre_loaded_tags.append(existing_ann.getTextValue())

    for ann in local_item.listAnnotations():
        remote_ann = None
        if ann.OMERO_TYPE == omero.model.TagAnnotationI:
            # There's an example with data from a batch export.
            # It uploads the tags with the image upload, and
            # then this adds duplicate ones.
            if not ann.getTextValue() in pre_loaded_tags:
                remote_ann = omero.gateway.TagAnnotationWrapper(remote_conn)
                remote_ann.setValue(ann.getTextValue())
        elif ann.OMERO_TYPE == omero.model.CommentAnnotationI:
            remote_ann = omero.gateway.CommentAnnotationWrapper(remote_conn)
            remote_ann.setValue(ann.getTextValue())
        elif ann.OMERO_TYPE == omero.model.LongAnnotationI:  # rating
            remote_ann = omero.gateway.LongAnnotationWrapper(remote_conn)
            remote_ann.setNs(ann.getNs())
            remote_ann.setValue(ann.getValue())
        elif ann.OMERO_TYPE == omero.model.MapAnnotationI:
            remote_ann = omero.gateway.MapAnnotationWrapper(remote_conn)
            remote_ann.setNs(ann.getNs())
            remote_ann.setValue(ann.getValue())
        elif ann.OMERO_TYPE == omero.model.FileAnnotationI:
            file_to_upload = ann.getFile()
            file_path = os.path.join(file_to_upload.getPath(),
                                     file_to_upload.getName())
            mime = file_to_upload.getMimetype()
            namespace = ann.getNs()
            description = ann.getDescription()
            remote_ann = remote_conn.createFileAnnfromLocalFile(
                file_path, mimetype=mime, ns=namespace, desc=description)
            # TODO this message would be better if it said if adding to image or dataset
            print "Attaching FileAnnotation to Item: ", "File ID:",\
                remote_ann.getId(),  ",", remote_ann.getFile().getName(), \
                "Size:", remote_ann.getFile().getSize()
        else:
            remote_ann = omero.gateway.CommentAnnotationWrapper(remote_conn)
            comment = 'Annotation of type: {} could not be uploaded.'.\
                format(ann.OMERO_TYPE)
            remote_ann.setValue(comment)
        if remote_ann:
            remote_ann.save()
            remote_item.linkAnnotation(remote_ann)


if __name__ == "__main__":
    run_script()
