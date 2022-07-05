import time
import utils
import re
import timeout_decorator

corosync_conf_path = '/etc/corosync/corosync.conf'
read_data = './corosync.conf'
crm_lincontrl_config = './crm_lincontrl_config'


class Host(object):
    def __init__(self, conn=None):
        self.conn = conn

    def modify_hostname(self, hostname):
        cmd = f'hostnamectl set-hostname {hostname}'
        utils.exec_cmd(cmd, self.conn)

    def modify_hostsfile(self, ip, hostname):
        cmd = f"sed -i 's/{ip}.*/{ip}\t{hostname}/g' /etc/hosts"
        utils.exec_cmd(cmd, self.conn)

    def get_hostname(self):
        return utils.exec_cmd('hostname', self.conn)

    # TODO ssh, remove
    # def check_ssh(self, cluster_hosts):
    #     # 1. 验证是否输入的host是否存在~/.ssh/authorized_keys这个文件
    #     # 2. 验证输入的hosts每个公钥最后的root@hostname, 是不是配置文件中都有记录
    #     ak_is_exist = bool(utils.exec_cmd('[ -f /root/.ssh/authorized_keys ] && echo True'))
    #     if not ak_is_exist:
    #         return
    #     if not self._check_authorized_keys(cluster_hosts):
    #         return
    #     return True

    # TODO ssh, remove
    # def _check_authorized_keys(self, cluster_hosts):
    #     authorized_keys = utils.exec_cmd('cat /root/.ssh/authorized_keys')
    #     hosts = re.findall('ssh-rsa\s[\s\S]*?\sroot@(.*)', authorized_keys)
    #     if set(cluster_hosts) <= set(hosts):
    #         return True

    def get_kernel_version(self):
        cmd = 'uname -r'
        return utils.exec_cmd(cmd, self.conn)

    def get_sys_version(self):
        cmd = 'lsb_release -a'
        result = utils.exec_cmd(cmd, self.conn)
        sys_version = re.findall('Description:\s*(.*)', result)
        if sys_version:
            return sys_version[0]

    def clear_ssh(self):
        cmd = 'rm ~/.ssh/*'
        utils.exec_cmd(cmd, self.conn)

    def apt_update(self):
        cmd = 'apt -y update'
        utils.exec_cmd(cmd, self.conn)

    def replace_linbit_sources(self):
        utils.exec_cmd('mv /etc/apt/sources.list /etc/apt/sources.list.x86bak', self.conn)
        utils.exec_cmd('echo "deb [trusted=yes] http://10.203.1.9:80/x86vm ./" > /etc/apt/sources.list', self.conn)

    def recovery_linbit_sources(self):
        utils.exec_cmd('mv /etc/apt/sources.list.x86bak /etc/apt/sources.list', self.conn)

    def replace_sources(self):
        utils.exec_cmd('mv /etc/apt/sources.list /etc/apt/sources.list.1bak', self.conn)
        utils.exec_cmd('echo "deb [trusted=yes] http://10.203.1.9:80/versaplx ./" > /etc/apt/sources.list', self.conn)

    def get_sources_list(self):
        cmd = f'find /etc/apt/sources.list.d -name "*.list"'
        result = utils.exec_cmd(cmd, self.conn)
        return result

    def bak_sources_list(self, name):
        cmd = f'mv {name} {name}.1bak'
        utils.exec_cmd(cmd, self.conn)


class Corosync(object):
    original_attr = {'cluster_name': 'debian',
                     'bindnetaddr': '127.0.0.1'}

    interface_pos = '''                ttl: 1
        }'''

    nodelist_pos = "logging {"

    def __init__(self, conn=None):
        self.conn = conn

    def sync_time(self):
        cmd = 'ntpdate -u ntp.api.bz'
        utils.exec_cmd(cmd, self.conn)

    def change_corosync_conf(self, cluster_name, bindnetaddr_list, interface, nodelist):
        # editor = utils.FileEdit(corosync_conf_path) # 读取原配置文件数据
        editor = utils.FileEdit(read_data)

        editor.replace_data(f"cluster_name: {self.original_attr['cluster_name']}", f"cluster_name: {cluster_name}")
        editor.replace_data(f"bindnetaddr: {self.original_attr['bindnetaddr']}", f"bindnetaddr: {bindnetaddr_list[0]}")
        editor.insert_data(interface, anchor=self.interface_pos, type='under')
        editor.insert_data(nodelist, anchor=self.nodelist_pos, type='above')
        if len(bindnetaddr_list) > 1:
            editor.insert_data(f'\trrp_mode: passive', anchor='        # also set rrp_mode.', type='under')

        utils.exec_cmd(f'echo "{editor.data}" > {corosync_conf_path}', self.conn)

    @timeout_decorator.timeout(30)
    def restart_corosync(self):
        cmd = 'systemctl restart corosync'
        utils.exec_cmd(cmd, self.conn)

    def check_ring_status(self, node):
        cmd = 'corosync-cfgtool -s'
        data = utils.exec_cmd(cmd, self.conn)
        ring_data = re.findall('RING ID\s\d*[\s\S]*?id\s*=\s*(.*)', data)
        for ip in node["heartbeat_line"]:
            if ip not in ring_data:
                return False
        return True

    def check_corosync_status(self, nodes, timeout=60):
        cmd = 'crm st | cat'
        t_beginning = time.time()
        node_online = []
        while not node_online:
            data = utils.exec_cmd(cmd, self.conn)
            node_online = re.findall('Online:\s\[(.*?)\]', data)
            if node_online:
                node_online = node_online[0].strip().split(' ')
                if set(node_online) == set(nodes):
                    return True
                else:
                    time.sleep(1)
            seconds_passed = time.time() - t_beginning
            if timeout and seconds_passed > timeout:
                return

    def get_version(self):
        cmd = 'corosync -v'
        result = utils.exec_cmd(cmd, self.conn)
        version = re.findall('version\s\'(.*)\'', result)
        if version:
            return version[0]

    def recover_conf(self):
        editor = utils.FileEdit(read_data)  # 恢复原始配置文件，需要read_data存在
        utils.exec_cmd(f'echo "{editor.data}" > {corosync_conf_path}', self.conn)

    def uninstall(self):
        cmd = 'apt purge -y corosync'
        utils.exec_cmd(cmd, self.conn)


class Pacemaker(object):
    def __init__(self, conn=None):
        self.conn = conn

    def modify_cluster_name(self, cluster_name):
        cmd = f"crm config property cluster-name={cluster_name}"
        utils.exec_cmd(cmd, self.conn)

    def modify_policy(self, status='stop'):
        cmd = f"crm config property no-quorum-policy={status}"
        utils.exec_cmd(cmd, self.conn)

    def modify_stonith_enabled(self):
        cmd = "crm config property stonith-enabled=false"
        utils.exec_cmd(cmd, self.conn)

    def modify_stickiness(self):
        cmd = "crm config rsc_defaults resource-stickiness=1000"
        utils.exec_cmd(cmd, self.conn)

    def restart(self):
        cmd = "systemctl restart pacemaker"
        utils.exec_cmd(cmd, self.conn)

    def check_crm_conf(self):
        cmd = 'crm config show | cat'
        data = utils.exec_cmd(cmd, self.conn)
        data_property = re.search('property cib-bootstrap-options:\s([\s\S]*)', data).group(1)
        # re_cluster_name = re.findall('cluster-name=(\S*)', data_property)
        re_stonith_enabled = re.findall('stonith-enabled=(\S*)', data_property)
        re_policy = re.findall('no-quorum-policy=(\S*)', data_property)
        re_resource_stickiness = re.findall('resource-stickiness=(\d*)', data)

        # 不进行cluster_name 的判断
        # if not re_cluster_name or re_cluster_name[0] != cluster_name:
        #     return

        if not re_stonith_enabled or re_stonith_enabled[0] != 'false':
            return

        if not re_policy or re_policy[0] not in ['ignore', 'stop']:
            return

        if not re_resource_stickiness or re_resource_stickiness[0] != '1000':
            return

        return True

    def install(self):
        cmd = 'apt install -y pacemaker crmsh corosync ntpdate'
        utils.exec_cmd(cmd, self.conn)

    def get_version(self):
        cmd = 'crm st | grep Current | cat'
        result = utils.exec_cmd(cmd, self.conn)
        version = re.findall('\(version\s(.*)\)\s', result)
        if version:
            return version[0]

    def config_drbd_attr(self):
        cmd1 = 'crm config primitive drbd-attr ocf:linbit:drbd-attr'
        cmd2 = 'crm config clone drbd-attr-clone drbd-attr'
        utils.exec_cmd(cmd1, self.conn)
        utils.exec_cmd(cmd2, self.conn)

    def clear_crm_res(self):
        utils.exec_cmd("crm res stop g_linstor p_fs_linstordb p_linstor-controller", self.conn)
        utils.exec_cmd("crm res stop ms_drbd_linstordb p_drbd_linstordb", self.conn)
        utils.exec_cmd("crm res stop drbd-attr", self.conn)
        utils.exec_cmd("crm res stop vipcontroller", self.conn)
        time.sleep(2)
        utils.exec_cmd("crm conf del g_linstor p_fs_linstordb p_linstor-controller", self.conn)
        utils.exec_cmd("crm conf del g_linstor ms_drbd_linstordb p_drbd_linstordb", self.conn)
        utils.exec_cmd("crm conf del drbd-attr", self.conn)
        utils.exec_cmd("crm conf del vipcontroller", self.conn)

    def clear_crm_node(self, node):
        utils.exec_cmd(f"crm conf del {node}", self.conn)

    def uninstall(self):
        cmd = 'apt purge -y pacemaker crmsh corosync ntpdate'
        utils.exec_cmd(cmd, self.conn)

    def set_vip(self, ip):
        cmd = f"crm cof primitive vipcontroller IPaddr2 params ip={ip} cidr_netmask=24 op monitor timeout=20 interval=10"
        utils.exec_cmd(cmd, self.conn)

    def colocation_vip_controller(self):
        cmd = "crm cof colocation c_vip_with_linstor inf: vipcontroller g_linstor"
        utils.exec_cmd(cmd, self.conn)


class TargetCLI(object):
    def __init__(self, conn=None):
        self.conn = conn

    def set_auto_add_default_portal(self):
        cmd = "targetcli set global auto_add_default_portal=false"
        utils.exec_cmd(cmd, self.conn)

    def set_auto_add_mapped_luns(self):
        cmd = "targetcli set global auto_add_mapped_luns=false"
        utils.exec_cmd(cmd, self.conn)

    def set_auto_enable_tpgt(self):
        cmd = "targetcli set global auto_enable_tpgt=true"
        utils.exec_cmd(cmd, self.conn)

    def check_targetcli_conf(self):
        cmd = "targetcli get global"
        data = utils.exec_cmd(cmd, self.conn)
        auto_add_default_portal = re.findall('auto_add_default_portal=(\w*)', data)
        auto_add_mapped_luns = re.findall('auto_add_mapped_luns=(\w*)', data)
        auto_enable_tpgt = re.findall('auto_enable_tpgt=(\w*)', data)

        if not auto_add_default_portal or auto_add_default_portal[0] != 'false':
            return False

        if not auto_add_mapped_luns or auto_add_mapped_luns[0] != 'false':
            return False

        if not auto_enable_tpgt or auto_enable_tpgt[0] != 'true':
            return False

        return True

    def install(self):
        cmd = 'apt install -y targetcli-fb'
        utils.exec_cmd(cmd, self.conn)

    def get_version(self):
        cmd = 'targetcli --version'
        result = utils.exec_cmd(cmd, self.conn)
        version = re.findall('version\s*(.*)', result)
        if version:
            return version[0]

    def uninstall(self):
        cmd = 'apt purge -y targetcli-fb'
        utils.exec_cmd(cmd, self.conn)


class ServiceSet(object):
    def __init__(self, conn=None):
        self.conn = conn

    def set_disable_drbd(self):
        cmd = 'systemctl disable drbd'
        utils.exec_cmd(cmd, self.conn)

    def set_disable_linstor_controller(self):
        cmd = 'systemctl disable linstor-controller'
        utils.exec_cmd(cmd, self.conn)

    def set_disable_targetctl(self):
        cmd = 'systemctl disable rtslib-fb-targetctl'
        utils.exec_cmd(cmd, self.conn)

    def set_enable_linstor_satellite(self):
        utils.exec_cmd("rm /etc/systemd/system/multi-user.target.wants/linstor-satellite.service", self.conn)
        cmd = 'systemctl enable linstor-satellite'
        utils.exec_cmd(cmd, self.conn)

    def set_enable_pacemaker(self):
        cmd = 'systemctl enable pacemaker'
        utils.exec_cmd(cmd, self.conn)

    def set_enable_corosync(self):
        cmd = 'systemctl enable corosync'
        utils.exec_cmd(cmd, self.conn)

    def check_status(self, name):
        cmd = f'systemctl is-enabled {name}'
        result = utils.exec_cmd(cmd, self.conn)
        if 'No such file or directory' in result:
            return
        if name == "rtslib-fb-targetctl":
            if 'disabled' in result:
                return 'disabled'
            else:
                return 'enabled'
        return result


class RA(object):
    def __init__(self, conn=None):
        self.conn = conn
        self.ra_path = self._get_ra_path()
        self.heartbeat_path = '/usr/lib/ocf/resource.d/heartbeat'
        self.ra_target = 'iSCSITarget.mod_cache_gena_acl_0'
        self.ra_logicalunit = 'iSCSILogicalUnit.450_patch1476_mod'

    def backup_iscsilogicalunit(self):
        cmd = f'mv {self.heartbeat_path}/iSCSILogicalUnit {self.heartbeat_path}/iSCSILogicalUnit.bak'
        if bool(utils.exec_cmd(f'[ -f {self.heartbeat_path}/iSCSILogicalUnit ] && echo True', self.conn)):
            utils.exec_cmd(cmd, self.conn)

    def backup_iscsitarget(self):
        cmd = f'mv {self.heartbeat_path}/iSCSITarget {self.heartbeat_path}/iSCSITarget.bak'
        if bool(utils.exec_cmd(f'[ -f {self.heartbeat_path}/iSCSITarget ] && echo True', self.conn)):
            utils.exec_cmd(cmd, self.conn)

    def cp_ra(self):
        cmd = 'cp %s/* %s/' % (self.ra_path, self.heartbeat_path)
        utils.exec_cmd(cmd, self.conn)

    def rename_ra(self):
        cmd = f'mv {self.heartbeat_path}/{self.ra_target} {self.heartbeat_path}/iSCSITarget;' \
              f'mv {self.heartbeat_path}/{self.ra_logicalunit} {self.heartbeat_path}/iSCSILogicalUnit'

        if bool(utils.exec_cmd(f'[ -f {self.heartbeat_path}/{self.ra_logicalunit} ] && echo True')) \
                and bool(utils.exec_cmd(f'[ -f {self.heartbeat_path}/{self.ra_logicalunit} ] && echo True')):
            utils.exec_cmd(cmd)

    def scp_ra(self, hostname):
        cmd = f'scp {self.heartbeat_path}/iSCSITarget {self.heartbeat_path}/iSCSILogicalUnit {hostname}:{self.heartbeat_path}/'
        utils.exec_cmd(cmd, self.conn)

    def check_ra_logicalunit(self):
        cmd = f'grep -rs "#{self.ra_logicalunit}" {self.heartbeat_path}/iSCSILogicalUnit'
        result = utils.exec_cmd(cmd, self.conn)
        if result:
            return True

    def check_ra_target(self):
        cmd = f'grep -rs "#{self.ra_target}" {self.heartbeat_path}/iSCSITarget'
        result = utils.exec_cmd(cmd, self.conn)
        if result:
            return True

    def _get_ra_path(self):
        # list_path_now = sys.path[0].split('/')
        # list_path_now.pop(-1)
        # list_path_now.append('RA')
        # ra_path = '/'.join(list_path_now)

        ra_path = '../RA'

        return ra_path

    def recover(self):
        # 使用备份的文件

        # iSCSILogicalUnit
        cmd1 = f'mv {self.heartbeat_path}/iSCSILogicalUnit.bak {self.heartbeat_path}/iSCSILogicalUnit'
        if bool(utils.exec_cmd(f'[ -f {self.heartbeat_path}/iSCSILogicalUnit.bak ] && echo True', self.conn)):
            utils.exec_cmd(cmd1, self.conn)

        # iSCSITarget
        cmd2 = f'mv {self.heartbeat_path}/iSCSITarget.bak {self.heartbeat_path}/iSCSITarget'
        if bool(utils.exec_cmd(f'[ -f {self.heartbeat_path}/iSCSITarget.bak ] && echo True', self.conn)):
            utils.exec_cmd(cmd2, self.conn)


class HALinstorController(object):
    stencil = """primitive p_drbd_linstordb ocf:linbit:drbd \
        params drbd_resource=linstordb \
        op monitor interval=29 role=Master \
        op monitor interval=30 role=Slave \
        op start interval=0 timeout=240s \
        op stop interval=0 timeout=100s
primitive p_fs_linstordb Filesystem \
        params device="/dev/drbd/by-res/linstordb/0" directory="/var/lib/linstor" fstype=ext4 \
        op start interval=0 timeout=60s \
        op stop interval=0 timeout=100s \
        op monitor interval=20s timeout=40s
primitive p_linstor-controller systemd:linstor-controller \
        op start interval=0 timeout=100s \
        op stop interval=0 timeout=100s \
        op monitor interval=30s timeout=100s
group g_linstor p_fs_linstordb p_linstor-controller
ms ms_drbd_linstordb p_drbd_linstordb \
        meta master-max=1 master-node-max=1 clone-max=3 clone-node-max=1 notify=true
colocation c_linstor_with_drbd inf: g_linstor ms_drbd_linstordb:Master
order o_drbd_before_linstor inf: ms_drbd_linstordb:promote g_linstor:start"""

    def __init__(self, conn=None):
        self.conn = conn

    def linstor_is_conn(self):
        cmd_result = utils.exec_cmd('linstor n l', self.conn)
        if not 'Connection refused' in cmd_result:
            return True

    def pool_is_exist(self, list_node, sp):
        cmd = f'linstor sp l -s {sp} | cat'
        pool_table = utils.exec_cmd(cmd, self.conn)
        for node in list_node:
            if not node in pool_table:
                return False
        return True

    def create_rd(self, name):
        cmd = f"linstor resource-definition create {name}"
        utils.exec_cmd(cmd, self.conn)

    def create_vd(self, name, size):
        cmd = f"linstor volume-definition create {name} {size}"
        utils.exec_cmd(cmd, self.conn)

    def create_res(self, name, node, sp):
        cmd = f"linstor resource create {node} {name} --storage-pool {sp}"
        utils.exec_cmd(cmd, self.conn)

    def delete_rd(self, name):
        cmd = f"linstor rd d {name}"
        utils.exec_cmd(cmd, self.conn)

    def stop_controller(self):
        cmd = f"systemctl stop linstor-controller"
        utils.exec_cmd(cmd, self.conn)

    def backup_linstor(self, backup_path):
        """
        E.g: backup_path = 'home/samba' 文件夹
        """
        if 'No such file or directory' in utils.exec_cmd(f"ls {backup_path}", self.conn):
            utils.exec_cmd(f'mkdir -p {backup_path}', self.conn)
        if not backup_path.endswith('/'):
            backup_path += '/'
        cmd = f"rsync -avp /var/lib/linstor {backup_path}"
        if not bool(utils.exec_cmd(f'[ -d {backup_path} ] && echo True', self.conn)):
            utils.exec_cmd(f"mkdir -p {backup_path}")
        utils.exec_cmd(cmd, self.conn)

    def get_controller(self):
        data = utils.exec_cmd("crm st | cat", self.conn)
        controller = re.findall("Masters: \[\s(\w*)\s\]", data)
        if controller:
            return controller[0]

    def is_active_controller(self):
        cmd_result = utils.exec_cmd("systemctl status linstor-controller | cat", self.conn)
        status = re.findall('Active:\s(\w*)\s', cmd_result)
        if status and status[0] == 'active':
            return True

    def move_database(self, backup_path):
        if backup_path.endswith('/'):
            backup_path = backup_path[:-1]

        cmd_mkfs = "mkfs.ext4 /dev/drbd/by-res/linstordb/0"
        cmd_rm = "rm -rf /var/lib/linstor/*"
        cmd_mount = "mount /dev/drbd/by-res/linstordb/0 /var/lib/linstor"
        cmd_rsync = f"rsync -avp {backup_path}/linstor/ /var/lib/linstor/"

        utils.exec_cmd(cmd_mkfs, self.conn)
        utils.exec_cmd(cmd_rm, self.conn)
        utils.exec_cmd(cmd_mount, self.conn)
        utils.exec_cmd(cmd_rsync, self.conn)

    def add_linstordb_to_pacemaker(self, clone_max):
        self.stencil = self.stencil.replace(f'clone-max=3', f'clone-max={clone_max}')
        utils.exec_cmd(f"echo -e '{self.stencil}' > crm_lincontrl_config", self.conn)
        cmd = "crm config load update crm_lincontrl_config"
        utils.exec_cmd(cmd, self.conn)
        # 这里可以设置删除这个文件，但好像没有必要

    def check_linstor_controller(self, list_node):
        data = utils.exec_cmd('crm st | cat', self.conn)
        p_fs_linstordb = re.findall('p_fs_linstordb\s*\(ocf::heartbeat:Filesystem\):\s*(.*)', data)
        p_linstor_controller = re.findall('p_linstor-controller\s*\(systemd:linstor-controller\):\s*(.*)', data)
        masters = re.findall('Masters:\s\[\s(\w*)\s]', data)
        slaves = re.findall('Slaves:\s\[\s(.*)\s]', data)

        if not p_fs_linstordb or 'Started' not in p_fs_linstordb[0]:
            return
        if not p_linstor_controller or 'Started' not in p_linstor_controller[0]:
            return
        if not masters and len(masters) != 1:
            return
        if not slaves:
            return

        slaves = slaves[0].split(' ')
        all_node = []
        all_node.extend(masters)
        all_node.extend(slaves)
        if set(all_node) != set(list_node):
            return
        return True

    def check_linstor_file(self, path):
        data = utils.exec_cmd(f'ls -l {path}')
        if 'linstordb.mv.db' in data and \
                'linstordb.trace.db' in data and \
                'loop_device_mapping' in data:
            return True

    def get_linstordb_lv(self):
        cmd = 'lvs /dev/*/linstordb* -o lv_name,vg_name --noheadings'
        lv_data = utils.exec_cmd(cmd, self.conn)
        list_lv = []
        if lv_data and not 'invalid characters' in lv_data:
            lv_all = re.findall('\s*(\w*)\s(\w*)', lv_data)
            if lv_all:
                list_lv = [f"/dev/{lv[1]}/{lv[0]}" for lv in lv_all]
        return list_lv

    def remove_lv(self, list_lv):
        """
        删除指定的lv，最后返回删除失败（已挂载）的lv列表
        :param lv_dict: E.g {'lv01':'vg01','lv02':'vg01'}
        :return:
        """

        fail_list = []
        for lv in list_lv:
            cmd = f"lvremove {lv} -y"
            cmd_result = utils.exec_cmd(cmd, self.conn)
            if 'in use' in cmd_result:
                fail_list.append(lv)

        return fail_list  # 返回已挂载而导致无法删除的lv

    def umount_lv(self, list_lv):
        for lv in list_lv:
            cmd = f'umount {lv}'
            utils.exec_cmd(cmd, self.conn)

    def secondary_drbd(self, drbd):
        cmd = f'drbdadm secondary {drbd}'
        utils.exec_cmd(cmd, self.conn)

    def modify_satellite_service(self):
        """
        配置 linstor-satellite systemd 让它开启的时候不要删掉 linstordb 的配置文件，解决机器重启后 linstor not install 的报错问题
        @return:
        """
        satellite_conf = "/etc/systemd/system/multi-user.target.wants/linstor-satellite.service"
        conf_data = utils.exec_cmd(f"cat {satellite_conf}", self.conn)
        if not "Environment=LS_KEEP_RES=linstordb" in conf_data:
            utils.exec_cmd(f"echo '[Service]' >> {satellite_conf}", self.conn)
            utils.exec_cmd(f"echo 'Environment=LS_KEEP_RES=linstordb' >> {satellite_conf}", self.conn)
            utils.exec_cmd(f"systemctl daemon-reload", self.conn)
            utils.exec_cmd(f"systemctl restart linstor-satellite", self.conn)

    def check_satellite_settings(self):
        # 配置文件检查
        satellite_conf = "/etc/systemd/system/multi-user.target.wants/linstor-satellite.service"
        conf_data = utils.exec_cmd(f"cat {satellite_conf}", self.conn)
        if not "Environment=LS_KEEP_RES=linstordb" in conf_data:
            return False

        # symbolic link 检查
        cmd_result = utils.exec_cmd("file /etc/systemd/system/multi-user.target.wants/linstor-satellite.service",
                                    self.conn)
        if not "symbolic link to" in cmd_result:
            return False
        return True


class DRBD(object):
    def __init__(self, conn=None):
        self.conn = conn

    def install_spc(self, times=8):
        """
        Can access the PPA source of LINSTOR to download their version
        """
        cmd1 = 'apt install -y software-properties-common'
        cmd2 = 'add-apt-repository -y ppa:linbit/linbit-drbd9-stack'
        utils.exec_cmd(cmd1, self.conn)
        time.sleep(2)
        utils.exec_cmd(cmd2, self.conn)
        while not self.is_exist_linbit_ppa():
            if self.conn:
                print(f'{self.conn._host}: failed to add linbit ppa，retry ...')
            else:
                print("localhost: failed to add linbit ppa，retry ...")
            utils.exec_cmd(cmd1, self.conn)
            utils.exec_cmd(cmd2, self.conn)
            times -= 1
            if times <= 0:
                return False
        return True

    def is_exist_linbit_ppa(self):
        cmd = 'find /etc/apt/sources.list.d/ -name "linbit-ubuntu-linbit-drbd9-stack-bionic.list"'
        if utils.exec_cmd(cmd, self.conn):
            return True

    def install_drbd(self):
        cmd = 'export DEBIAN_FRONTEND=noninteractive && apt install -y drbd-utils drbd-dkms'
        utils.exec_cmd(cmd, self.conn)

    def get_version(self):
        cmd = 'drbdadm --version'
        result = utils.exec_cmd(cmd, self.conn)
        version_kernel = re.findall('DRBD_KERNEL_VERSION=(.*)', result)
        # version_drbdadm = re.findall('')
        if version_kernel:
            return version_kernel[0]

    def uninstall(self):
        cmd = 'apt purge -y software-properties-common && apt purge -y drbd-utils drbd-dkms'
        utils.exec_cmd(cmd, self.conn)


class Linstor(object):
    def __init__(self, conn=None):
        self.conn = conn

    def create_conf(self, ips):
        conf_data = f"[global]\ncontrollers={ips}"  # ips逗号分割
        cmd = f'echo "{conf_data}" > /etc/linstor/linstor-client.conf'
        utils.exec_cmd(cmd, self.conn)

    def start_controller(self, status='start', timeout=30):
        cmd = f"systemctl {status} linstor-controller"
        utils.exec_cmd(cmd, self.conn)
        t_beginning = time.time()
        while True:
            time.sleep(1)
            result = utils.exec_cmd("linstor n l", self.conn)
            if "Connection refused" not in result:
                break
            seconds_passed = time.time() - t_beginning
            if timeout and seconds_passed > timeout:
                return False

    def start_satellite(self, status='start'):
        cmd = f"systemctl {status} linstor-satellite"
        utils.exec_cmd(cmd, self.conn)

    def create_node(self, node, ip, type='Combined'):
        cmd = f'linstor node create {node} {ip}  --node-type {type}'
        utils.exec_cmd(cmd, self.conn)

    def create_lvm_sp(self, node, vg, sp):
        cmd = f'linstor storage-pool create lvm {node} {sp} {vg}'
        utils.exec_cmd(cmd, self.conn)

    def create_lvmthin_sp(self, node, lv, sp):
        cmd = f'linstor storage-pool create lvmthin {node} {sp} {lv}'
        utils.exec_cmd(cmd, self.conn)

    def install(self):
        cmd = 'apt install -y linstor-controller linstor-satellite linstor-client'
        utils.exec_cmd(cmd, self.conn)

    def get_version(self):
        cmd = 'linstor --version'
        result = utils.exec_cmd(cmd, self.conn)
        version = re.findall('linstor (.*);', result)
        if version:
            return version[0]

    def clear(self):
        utils.exec_cmd('rm -rf /etc/linstor/linstor-client.conf', self.conn)

    def uninstall(self):
        cmd = 'apt purge -y  linstor-controller linstor-satellite linstor-client'
        utils.exec_cmd(cmd, self.conn)


class LVM(object):
    def __init__(self, conn=None):
        self.conn = conn

    def pv_create(self, disk):
        cmd = f'pvcreate {disk}'
        result = utils.exec_cmd(cmd, self.conn)
        if 'successfully created' in result:
            return True

    def vg_create(self, vg, pv):
        cmd = f'vgcreate {vg} {pv} -y'
        utils.exec_cmd(cmd, self.conn)

    def thinpool_create(self, vg, lv):
        create_cmd = f'lvcreate -T -l 90%VG -n {lv} {vg} -y'
        utils.exec_cmd(create_cmd, self.conn)
        extend_cmd = f'lvextend -l +100%FREE /dev/{vg}/{lv} -y'
        utils.exec_cmd(extend_cmd, self.conn)

    def install(self):
        cmd = 'apt install -y lvm2'
        utils.exec_cmd(cmd, self.conn)

    def uninstall(self):
        cmd = 'apt purge -y lvm2'
        utils.exec_cmd(cmd, self.conn)

    def remove_vg(self, vg):
        return utils.exec_cmd(f"vgremove -y {vg}", self.conn)
