class Device(object):
    @classmethod
    def fromxml(cls, findall):
        return []
        
class ETHDevice(Device):
    pass

class ETHNetworkDevice(ETHDevice):
    def __init__(self, hw, tdev, network='default', mode='nat', ip=None):
        self.hw = hw.upper()
        self.tdev = tdev
        self.mode = mode
        self.network = network
        self.ip = ip
    
    def toxml(self, root):
        with root.interface(type='network'):
            root.source(network=self.network)
            root.forward(mode=self.mode)
            root.target(dev=self.tdev)
            root.mac(address=self.hw)

    @classmethod
    def fromxml(cls, findall):
        for obj in findall("devices/interface[@type='network']"):
            yield cls(
                obj.find('mac').attrib['address'],
                obj.find('target').attrib['dev'],
                obj.find('source').attrib['network'])
        
class ETHBridgedDevice(ETHDevice):
    def __init__(self, hw, tdev, bridge, ip=None):
        self.hw = hw.upper()
        self.tdev = tdev
        self.bridge = bridge
        self.ip = ip
    
    def toxml(self, root):
        with root.interface(type='bridge'):
            root.source(bridge=self.bridge)
            root.target(dev=self.tdev)
            root.mac(address=self.hw)

    @classmethod
    def fromxml(cls, findall):
        for obj in findall("devices/interface[@type='bridge']"):
            yield cls(
                obj.find('mac').attrib['address'],
                obj.find('target').attrib['dev'],
                obj.find('source').attrib['bridge'])
 
class FileSystemDevice(Device):
    def __init__(self, source, target='/', type='mount'):
        self.type = type
        self.source = source
        self.target = target
    
    def toxml(self, root):
        with root.filesystem(type='mount'):
            root.source(dir=self.source)
            root.target(dir=self.target)
        
class HDDBlockDevice(Device):
    def __init__(self, dev_path,
                       type_ = 'raw',
                       driver='qemu',
                       device='disk',
                       dev = 'vda',
                       bus = 'virtio'):
        self.dev_path = dev_path
        self.type_ = type_
        self.driver = driver
        self.device = device
        self.dev = dev
        self.bus = bus

    @classmethod
    def cdrom(cls, path):
        return cls(path, 'block', device = 'cdrom', dev = 'vdc')

    def toxml(self, root):
        with root.disk(device=self.device, type='block'):
            root.driver(type=self.type_, name=self.driver)
            root.source(dev=self.dev_path)
            root.boot
            root.target(bus=self.bus, dev=self.dev)

class HDDFileDevice(Device):
    def __init__(self, image_path,
                       type_ = 'raw',
                       driver='qemu',
                       device='disk',
                       dev = 'vda',
                       bus = 'virtio'):
        self.image_path = image_path
        self.type_ = type_
        self.driver = driver
        self.device = device
        self.dev = dev
        self.bus = bus

    @classmethod
    def cdrom(cls, path):
        return cls(path, 'file', device = 'cdrom', dev = 'vdc')

    def toxml(self, root):
        with root.disk(device=self.device, type='file'):
            root.driver(type=self.type_, name=self.driver)
            root.source(file=self.image_path)
            root.target(bus=self.bus, dev=self.dev)

