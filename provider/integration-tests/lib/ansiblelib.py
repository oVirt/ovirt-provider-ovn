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

from __future__ import absolute_import

import ansible_runner
import os

COMMON_PLAYBOOK_VARS = {
    'provider_container_id': os.environ['PROVIDER_CONTAINER_ID'],
    'controller_container_id': os.environ['CONTROLLER_CONTAINER_ID']
}

PLAYBOOK_DIR = os.path.join(os.environ['INTEG_TEST_ROOT_FOLDER'], 'ansible')
PY_INTERPRETER = os.environ['PY_INTERPRETER']


def get_playbook(playbook_name, playbook_vars):
    playbook_vars.update(COMMON_PLAYBOOK_VARS)
    playbook_path = os.path.join(PLAYBOOK_DIR, playbook_name)
    return Playbook(playbook_path, extra_vars=playbook_vars)


class AnsibleExecutionFailure(Exception):
    pass


class Playbook(object):
    def __init__(self, playbook, extra_vars=None):
        self._execution_stats = None
        self._idempotency_check_stats = None
        self._playbook = playbook
        self._extra_vars = extra_vars or {}

    @property
    def execution_stats(self):
        return self._execution_stats

    @property
    def idempotency_check_stats(self):
        return self._idempotency_check_stats

    def run(self, enable_idempotency_checker=True):
        self._execution_stats = self._run_playbook_executor()
        if enable_idempotency_checker:
            self._idempotency_check_stats = self._run_playbook_executor()
        self._assert_playbook_executed_successfully(enable_idempotency_checker)

    def _run_playbook_executor(self):
        runner = ansible_runner.run(
            playbook=self._playbook,
            extravars=self._extra_vars,
            inventory='localhost ansible_connection=local '
                      'ansible_python_interpreter={}'.format(PY_INTERPRETER)
        )
        if runner.status != 'successful':
            raise AnsibleExecutionFailure
        return Playbook._stats(runner)

    @staticmethod
    def _stats(runner):
        last_event = list(
            filter(
                lambda x:
                'event' in x and x['event'] == 'playbook_on_stats',
                runner.events
            )
        )
        if not last_event:
            return None
        last_event = last_event[0]['event_data']
        return dict(skipped=last_event['skipped'],
                    ok=last_event['ok'],
                    dark=last_event['dark'],
                    failures=last_event['failures'],
                    processed=last_event['processed'],
                    changed=last_event['changed'])

    def _assert_playbook_executed_successfully(self, check_idempotency):
        assert not self.execution_stats['failures']
        assert self.execution_stats['changed'].get('localhost', 0) > 0
        if check_idempotency:
            assert not self._idempotency_check_stats['failures']
            assert not self._idempotency_check_stats['changed']
