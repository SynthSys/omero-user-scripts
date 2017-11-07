import omero
from omero.gateway import BlitzGateway
from path import path
import sys
import subprocess

file_loc = "/Users/eilidhtroup/omero/ManagedRepository/root_0/2017-10/06/" \
           "16-21-46.945/antibiotic_plate.jpg"

# remote
username = "etroup"
password = "eilidhg"
remote_host = 'demo.openmicroscopy.org'
remote_port = 4064

# # Connect to remote server.
# remote_conn = BlitzGateway(username, password, host=host, port=port)
# connected = remote_conn.connect() # returns true if connected
#
# if (connected):
#    print "connected"
#    for p in remote_conn.listProjects():
#        print p.getName()
# else:
#    print "not connected"
#
# remote_conn.close()

c = omero.client(host=remote_host, port=remote_port, args=["--Ice.Config=/dev/null"])
c.createSession(username, password)
############
key = c.getSessionId()

args = [sys.executable]
args.append(str(path(".") / "bin" / "omero"))
args.extend(["-s", remote_host, "-k", key, "-p", str(remote_port), "import"])
args.append(file_loc)

print "args are"
print args

# TODO could get omero_dist as done in def omerodistdir(cls):
# from https://github.com/openmicroscopy/openmicroscopy/blob/develop/components/tools/OmeroPy/src/omero/testlib/__init__.py#L277
popen = subprocess.Popen(args, #cwd=str(self.omero_dist),
                            cwd="/Users/eilidhtroup/Documents/SynthSysDataManagement/omero/omeroServer/OMERO.server",
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
out, err = popen.communicate()
rc = popen.wait()
if rc != 0:
    raise Exception("import failed: [%r] %s\n%s" % (args, rc, err))
pix_ids = []
for x in out.split("\n"):
    if x and x.find("Created") < 0 and x.find("#") < 0:
        try:    # if the line has an image ID...
            image_id = str(long(x.strip()))
            # Occasionally during tests an id is duplicated on stdout
            if image_id not in pix_ids:
                pix_ids.append(image_id)
        except:
            pass

print "pix_ids"
print pix_ids

############
try:
    remote_conn = BlitzGateway(client_obj=c)
    for p in remote_conn.getObjects("Project"):
	    print p.id, p.name

    # Transfer image over

    # Your script, running on the OMERO server * may * be able to access the
    # managed repository directly, and call
    # e.g. ?bin/omero import /OMERO/ManagedRepository/will_3/2017-10/05/15-31-34.090/control.lsm

finally:
    c.closeSession()
    remote_conn.close()