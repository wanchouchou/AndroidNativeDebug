#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: zouwei
# @Email: wanchouchoumobsec@gmail.com
# @Last Modified by:   zouwei
# @Last Modified time: 2016-02-11 00:14:49


from adb import ADB
import sys
from sys import stdin, exit
import os
import subprocess
from Config import CONFIG


NEED_RESTART_ADB = True
INIT_TIMES = 5


class ADB_Wrapper(object):

    def __init__(self, adb_path):
        self.adb_path = adb_path
        self.adb = None
        self.devices = []

        self.adb = ADB(adb_path)
        if NEED_RESTART_ADB:
            self.restart_adb()

    def restart_adb(self):
        print '[+] Restarting ADB server as ROOT...'
        self.adb.set_adb_root(1)
        if self.adb.lastFailed():
            print '\t Restart ADB ERROR\n'
            exit(-3)
        print 'Restart ADB as ROOT successed!'

    def get_detected_devices(self):
        self.devices = None
        dev = 0
        while dev is 0:
            print '[+] Detecting devices...'
            error, devices = self.adb.get_devices()

            if error is 1:
                print 'No devices connnected'
                print '[+] Waiting for deices...'
                self.adb.wait_for_device()
                continue

            elif error is 2:
                print "You haven't enought permissions!"
                exit(-3)

            # If devices is ['*', 'deamon', 'start', 'successfully'.....],
            # means that we should restart adb untill we get valid devices
            if len(devices) > 3 and devices[0] == '*' and devices[1] == 'daemon':
                print '[W] get devices error, we should restart the adb'
                continue
            print '[+] Get devices successfully'
            self.devices = devices
            dev = 1

    def set_target_device(self):

        devices_count = 0
        for dev in self.devices:
            print '\t%d: %s' % (devices_count, dev)
            if dev != 'offline':
                devices_count += 1

        # For the cmd 'adb forward ......' can exec successly only when there is one device/emulator,
        # so if there are more than one devices, we exit.
        if devices_count > 1:
            print '[Error] More than one devices/emulators, please shut down others!'
            exit(-3)

        # set target device
        dev_index = 0
        try:
            self.adb.set_target_device(self.devices[dev_index])
        except Exception, e:
            print '[E] Set target devices error, error info:', e
            print '==== Do not warry, just try again!==='
            exit(-5)

        print "\n[+] Using '%s' as target device" % self.devices[dev_index]


class Apk_manager(object):

    def __init__(self, adb, adb_path, apk_path, aapt_path):
        self.value = ''
        self.pos = 0
        self.adb_path = adb_path
        self.apk_path = apk_path
        self.aapt_path = aapt_path
        self.data = ''
        self.adb = adb

    def is_apk_exist(self):
        if os.path.exists(self.apk_path):
            return True
        else:
            print '[E] Find apk failed!'
            return False

    def init_apk_info(self, aapt_path):
        if self.is_apk_exist() is False:
            self.data = ''
            return ''
        if aapt_path is None:
            print '[E] Must set the path of aapt in Config.py!'
            self.data = ''
            return ''
        get_info_cmd = self.aapt_path + ' d badging ' + self.apk_path
        try:
            self.data = os.popen(get_info_cmd).read()
        except Exception, e:
            print '[E] Exec cmd: %s failed!' % get_info_cmd
            print e
            self.data = ''

        return ''

    def get_content(self, mark):
        data = self.data
        markIndex = data[self.pos:].index(mark)
        firstSinglequotesIndex = markIndex + len(mark) + self.pos
        lastSinglequotesIndex = data[
            firstSinglequotesIndex + 1:].index('\'') + firstSinglequotesIndex + 1
        self.value = data[firstSinglequotesIndex + 1: lastSinglequotesIndex]
        self.pos = lastSinglequotesIndex

    def get_packagename(self):
        if self.data == '':
            return ''
        package_mark = 'package: name='
        self.get_content(package_mark)
        print '[+] PackageName is \'', self.value, '\''
        return self.value

    def get_mainactivity(self):
        if self.data == '':
            return ''

        mainactivity_mark = 'launchable-activity: name='
        self.get_content(mainactivity_mark)
        print '[+] MainActivity is \'', self.value, '\''
        return self.value

    def __build_command__(self, cmd):
        ret = self.adb_path + ' ' + cmd
        if sys.platform.startswith('win'):
            return ret
        else:
            ret = ret.split()

        return ret

    def install_apk(self):
        print '[+] Install apk: %s' % os.path.basename(self.apk_path)
        if self.is_apk_exist() is False:
            print '[E] The apk: %s is not exists!' % self.apk_path
            exit(-3)
        # Do not use adb.run_cmd when installing the apk, please
        # look at the Abdroid_native_debug.exec_android_server() for
        # details reason
        cmd = self.__build_command__(' install -f ' + self.apk_path)
        adb_process = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # if i use read() instead of readline, this function maybe block. I don't
        # know why~
        ret_line = adb_process.stdout.readline()
        print '[+] ' + ret_line.strip('\n')
        print '[W]\tInstalling......\n\tNow you maybe need to wait several seconds, please be patient......'
        ret_line = adb_process.stdout.readline()
        print '[+]\t' + ret_line.strip('\n')

    def launch_apk(self):
        self.init_apk_info(self.aapt_path)
        package_name = self.get_packagename()
        mainactivity_name = self.get_mainactivity()
        if package_name == '' or mainactivity_name == '':
            print '[ERROR] get package/MainActivity name failed!'
            return
        startAppCMD = 'am start -D -n ' + \
            package_name + '/' + mainactivity_name
        self.adb.shell_command(startAppCMD)

        # wait for user attaching the target process in IDA
        print '[W]=== Now please attach process \'%s\' in IDA' % package_name


class Android_native_debug(object):

    def __init__(self, apk_path, adb_path, aapt_path, andServer_path):
        self.apk_path = apk_path
        self.adb_path = adb_path
        self.aapt_path = aapt_path
        self.andServer_path = andServer_path
        # adb_wrapper init
        self.adb_wrapper = ADB_Wrapper(adb_path)
        self.adb_wrapper.get_detected_devices()
        self.adb_wrapper.set_target_device()
        self.adb_connect_check()
        # apk_manager init
        self.apk_manager = Apk_manager(
            self.adb_wrapper.adb, self.adb_path, self.apk_path, self.aapt_path)

        self.is_emulator = self.is_target_emulator()
        self.adb_server_process = None

    def adb_connect_check(self):
        '''
        After we initialied an instance of Adb_Wrapper, we should check if it is working well.
        If not, we must initial it again. Considering with the case that we do not need to
        restart the adb while we re-initial it, so we set the global flag 'NEED_RESTART_ADB' to False.
        '''
        global NEED_RESTART_ADB, INIT_TIMES
        print '[+] Checking the state of the adb connnect......'
        adb_shell_args_test = 'ls -l /'
        ret = self.adb_wrapper.adb.shell_command(adb_shell_args_test)
        if ret is None and INIT_TIMES > -1:
            # we should re-init
            print '[W] Init Android_native_debug falied, try again.'
            NEED_RESTART_ADB = False
            INIT_TIMES -= 1
            if INIT_TIMES < 0:
                print '[E] Can not create adb connect with the device. MUST EXIT!!!'
                exit(-3)
            self.__init__()

        else:
            print '[+] adb connnected well!'

    def __build_command__(self, cmd):
        ret = self.adb_path + ' ' + cmd
        if sys.platform.startswith('win'):
            return ret
        else:
            ret = ret.split()

        return ret

    def install_apk(self):
        self.apk_manager.install_apk()

    def is_androidServer_exist(self):
        base_cmd = 'ls -l /data/local/tmp'
        ret = self.run_adb_shellcmd(base_cmd)

        if ret != None and ret.find('my_android_server') > -1:
            print '[+] android_server is existed'
            return True

        return False

    def push_androidServer(self):
        cmd = 'push %s /data/local/tmp/my_android_server' % self.andServer_path
        self.run_adb_cmd(cmd)
        print '[+] push %s to /data/local/tmp/' % andServer_path

    def exec_android_server(self):
        if self.is_androidServer_exist():
            print '[W]=== Do you want to overwrite the android_server?(Y or Enter):'
            cmd = str(stdin.readline())
            if cmd.find('Y') > -1 or cmd.find('y') > -1:
                print '[+] You choose overwrite!'
                self.push_androidServer()
            else:
                print '[+] You choose NOT overwrite'
        else:
            self.push_androidServer()

        self.adb_forward()

        # exec_android_server
        shell_cmd = 'chmod 777 /data/local/tmp/my_android_server'
        self.run_adb_shellcmd(shell_cmd)

        print '[+] exec the my_android_server.'
        print '++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++'
        # The self.run_adb_shellcmd call adb.shell_command function which using subprocess.popen().communicate() to exec shell cmd.
        # But if the target cmd occur a block, such as this case :),
        # then we could not continue running other cmds.
        # To avoid this situation, I use subprocess.popen and manually read the
        # stdout instead of using subprocess.popen(..).communicate() 

        shell_cmd = '/data/local/tmp/my_android_server'
        cmd = self.adb_shell_cmd_wrapper(shell_cmd)
        cmd = self.__build_command__(' shell ' + cmd)
        adb_process = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # if i use read() instead of readline, this function maybe block.
        # I don't know why~
        ret_line = adb_process.stdout.readline()
        print '[+] ' + ret_line.strip('\n')
        print '[W] Now you maybe need to wait several seconds, please be patient......'
        ret_line = adb_process.stdout.readline()
        print '[+] ' + ret_line.strip('\n')
        if ret_line.find('bind') > -1:
            print '    (Don\'t be worry, It is also working well )'

    def adb_forward(self):
        print '[+] Begin adb port forwarding......'
        cmd = 'forward tcp:23946 tcp:23946 '
        self.run_adb_cmd(cmd)

    def is_target_emulator(self):
        target_dev = self.adb_wrapper.adb.get_target_device()
        if target_dev.find('emulator') > -1:
            print '[+] Target device is Emulator......'
            return True

        return False

    def get_pid_by_name(self, process_name):
        pid = ''
        ret = self.run_adb_shellcmd('ps')
        ret_list = ret.split('\n')  # split by '\n'
        for rl in ret_list:
            if rl.find(process_name) > -1:
                elements_list = rl.split(' ')  # split by space
                for i in xrange(1, len(elements_list), 1):
                    # The frist element must be 'root', so we find the send
                    # element which is not ''
                    if elements_list[i] != '':
                        pid = elements_list[i]
                        print '[+] the pid of %s is: %s' % (process_name, pid)
                        break

                if pid != '':
                    break

        return pid

    def kill_android_server(self):
        print '[W] Kill the android_server......'
        if self.adb_server_process is not None:
            self.adb_server_process.terminate()
        # first get the pid of my_android_server
        pid = self.get_pid_by_name(' /data/local/tmp/my_android_server')
        if pid != '':
            base_cmd = 'kill -9 %s' % pid
            self.run_adb_shellcmd(base_cmd)

    def adb_shell_cmd_wrapper(self, base_cmd):
        '''
        If some adb shell command need root permission,
        please use this function to wrapper the cmd.
        '''
        if self.is_emulator:
            return base_cmd
        else:
            return "su -c ' " + base_cmd + " ' "

    def run_adb_shellcmd(self, base_cmd, need_root_permission=True):
        if need_root_permission:
            cmd = self.adb_shell_cmd_wrapper(base_cmd)
        ret = self.adb_wrapper.adb.shell_command(cmd)
        print '[+] Exec %s .' % cmd
        return ret

    def run_adb_cmd(self, cmd):
        ret = self.adb_wrapper.adb.run_cmd(cmd)
        print '[+] Exec %s .' % cmd
        return ret

    def exec_apk_in_debugmode(self):
        print '++++++++++++++++++++++++++++++++++++++++++++++++'
        print '[+] Begin launch \'%s\' in debug mode......' % os.path.basename(self.apk_path)
        self.apk_manager.launch_apk()
        print "[W]=== Have you attached successfully?(N or Enter):"
        cmd = str(stdin.readline())
        if cmd.find('N') > -1 or cmd.find('n') > -1:
            print '[+] Attach failed, Please try again :)'
            # kill my_android_server
            self.kill_android_server()
            exit(-3)
        else:
            print '[W]=== Now you can open the DDMS and get the jdwp port of target process......'
            print '[W]=== Please input the jdwp port of target process:   '
            # NOTE: must strip by '\n'! Or the port will be 'xxx\n'
            port = str(stdin.readline()).strip('\n')
            self.connect_process_by_jdb(port)

    def connect_process_by_jdb(self, port):
        jdb_cmd = 'jdb -connect com.sun.jdi.SocketAttach:port=%s,hostname=localhost' % port
        print '[+] Exec %s' % jdb_cmd
        os.system(jdb_cmd)


if __name__ == '__main__':
    apk_path = CONFIG.APK_PATH
    adb_path = CONFIG.ADB_PATH
    aapt_path = CONFIG.AAPT_PATH
    andServer_path = CONFIG.HOST_ANDROIDSERVER_PATH

    android_native_debug = Android_native_debug(
        apk_path, adb_path, aapt_path, andServer_path)
    if len(sys.argv) > 1:
        android_native_debug.install_apk()
    android_native_debug.exec_android_server()
    android_native_debug.exec_apk_in_debugmode()
