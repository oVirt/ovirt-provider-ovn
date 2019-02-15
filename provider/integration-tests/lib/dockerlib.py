#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license

import subprocess


CONTAINER_CLI = 'docker'


def get_container_ip(container_name):
    docker_ip_command = [
        CONTAINER_CLI, 'inspect', '-f',
        '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
        container_name
    ]
    return subprocess.check_output(
        docker_ip_command, stderr=subprocess.STDOUT
    ).decode().strip()


def inner_ping(
        container_name, source_namespace, target_ip, expected_result=0,
        ip_version=4
):
    command = [
        CONTAINER_CLI, 'exec', container_name, 'bash', '-c',
        'ip netns exec {} ping -{} -c 1 {}'.format(
            source_namespace, ip_version, target_ip
        )
    ]
    result = subprocess.call(command)
    if result != expected_result:
        if expected_result == 0:
            reason = 'Connectivity issues'
        else:
            reason = 'Unexpected connectivity'
        raise Exception(reason)
    return result


def get_container_id_from_img_name(image_name):
    command = [
        CONTAINER_CLI, 'ps', '-q', '--filter',
        'ancestor={img}'.format(img=image_name)
    ]
    return subprocess.check_output(
        command, stderr=subprocess.STDOUT
    ).decode().strip()
