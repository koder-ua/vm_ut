import fcntl
import array
import struct
import socket
import platform

# global constants.  If you don't like 'em here,
# move 'em inside the function definition.
SIOCGIFCONF = 0x8912
MAXBYTES = 8096

def localifs():
    """
    Used to get a list of the up interfaces and associated IP addresses
    on this machine (linux only).

    Returns:
        List of interface tuples.  Each tuple consists of
        (interface name, interface IP)
    """
    global SIOCGIFCONF
    global MAXBYTES

    arch = platform.architecture()[0]

    # I really don't know what to call these right now
    var1 = -1
    var2 = -1
    if arch == '32bit':
        var1 = 32
        var2 = 32
    elif arch == '64bit':
        var1 = 16
        var2 = 40
    else:
        raise OSError("Unknown architecture: %s" % arch)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    names = array.array('B', '\0' * MAXBYTES)
    outbytes = struct.unpack('iL', fcntl.ioctl(
        sock.fileno(),
        SIOCGIFCONF,
        struct.pack('iL', MAXBYTES, names.buffer_info()[0])
        ))[0]

    namestr = names.tostring()
    return [(namestr[i:i+var1].split('\0', 1)[0], socket.inet_ntoa(namestr[i+20:i+24])) \
            for i in xrange(0, outbytes, var2)]

