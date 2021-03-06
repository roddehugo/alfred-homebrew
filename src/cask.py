# encoding: utf-8

import os
import sys
import subprocess

from workflow import Workflow, MATCH_SUBSTRING
from workflow.background import run_in_background

import cask_actions
import helpers


GITHUB_SLUG = 'fniephaus/alfred-homebrew'
OPEN_HELP = 'open https://github.com/fniephaus/alfred-homebrew && exit'
DEFAULT_SETTINGS = {
    'HOMEBREW_CASK_OPTS': {
        'appdir': '/Applications',
        'caskroom': '/usr/local/Caskroom'
    }
}


def execute(wf, command):
    if command not in ['search', 'list', 'alfred status']:
        return None

    opts = wf.settings.get('HOMEBREW_CASK_OPTS', None)
    cmd_list = ['brew', 'cask', command]
    if opts:
        if all(k in opts for k in ('appdir', 'caskroom')):
            cmd_list += ['--appdir=%s' % opts['appdir'],
                         '--caskroom=%s' % opts['caskroom']]

    new_env = os.environ.copy()
    new_env['PATH'] = '/usr/local/bin:%s' % new_env['PATH']
    result, err = subprocess.Popen(cmd_list,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   env=new_env).communicate()
    if err:
        return 'Error: %s' % err

    if 'sudo' in result:
        return 'Config'

    return result


def get_all_casks():
    return execute(wf, 'search').splitlines()[1:]


def get_installed_casks():
    return execute(wf, 'list').splitlines()


def filter_all_casks(wf, query):
    formulas = wf.cached_data('cask_all_casks',
                              get_all_casks,
                              max_age=3600)
    query_filter = query.split()
    if len(query_filter) > 1:
        return wf.filter(query_filter[1], formulas, match_on=MATCH_SUBSTRING)
    return formulas


def filter_installed_casks(wf, query):
    formulas = wf.cached_data('cask_installed_casks',
                              get_installed_casks,
                              max_age=3600)
    query_filter = query.split()
    if len(query_filter) > 1:
        return wf.filter(query_filter[1], formulas, match_on=MATCH_SUBSTRING)
    return formulas


def edit_settings(wf):
    # Create default settings if they not exist
    if (not os.path.exists(wf.settings_path) or
            not wf.settings.get('HOMEBREW_CASK_OPTS', None)):
        for key in DEFAULT_SETTINGS:
            wf.settings[key] = DEFAULT_SETTINGS[key]
    # Edit settings
    subprocess.call(['open', wf.settings_path])


def cask_installed(wf):
    return not execute(wf, 'search').startswith('Error')


def cask_configured(wf):
    return not execute(wf, 'search').startswith('Config')


def main(wf):
    if wf.update_available:
        wf.add_item('An update is available!',
                    autocomplete='workflow:update',
                    valid=False,
                    icon=helpers.get_icon(wf, 'cloud-download'))

    def _cask_installed():
        return cask_installed(wf)

    def _cask_configured():
        return cask_configured(wf)

    if not wf.cached_data('cask_installed', _cask_installed, max_age=0):
        wf.add_item('Cask does not seem to be installed!',
                    'Hit enter to see what you need to do...',
                    arg='open http://caskroom.io/ && exit',
                    valid=True,
                    icon='cask.png')
        wf.add_item('I trust this workflow',
                    'Hit enter to run `brew install caskroom/cask/brew-cask`'
                    ' to install cask...',
                    arg='brew install caskroom/cask/brew-cask',
                    valid=True,
                    icon='cask.png')
        # delete cached file
        wf.cache_data('cask_installed', None)
    elif not wf.cached_data('cask_configured', _cask_configured, max_age=0):
        wf.add_item('Cask does not seem to be properly configured!',
                    'Hit enter to see what you need to do...',
                    arg=OPEN_HELP,
                    valid=True,
                    icon='cask.png')

        config = next(a for a in cask_actions.ACTIONS if a.name == 'config')
        wf.add_item(config['name'], config['description'],
                    uid=config['name'],
                    autocomplete=config['autocomplete'],
                    arg=config['arg'],
                    valid=config['valid'],
                    icon=helpers.get_icon(wf, 'chevron-right'))

        query = wf.args[0] if len(wf.args) else None
        if query and query.startswith('config'):
            edit_settings(wf)
        # delete cached file
        wf.cache_data('cask_configured', None)
    else:
        # extract query
        query = wf.args[0] if len(wf.args) else None

        if query and query.startswith('install'):
            for formula in filter_all_casks(wf, query):
                wf.add_item(formula, 'Install cask',
                            arg='brew cask install %s' % formula,
                            valid=True,
                            icon=helpers.get_icon(wf, 'package'))
        elif query and any(query.startswith(x) for x in ['search', 'home']):
            for formula in filter_all_casks(wf, query):
                wf.add_item(formula, 'Open homepage',
                            arg='brew cask home %s' % formula,
                            valid=True,
                            icon=helpers.get_icon(wf, 'package'))
        elif query and query.startswith('uninstall'):
            for formula in filter_installed_casks(wf, query):
                name = formula.split(' ')[0]
                wf.add_item(formula, 'Uninstall cask',
                            arg='brew cask uninstall %s' % name,
                            valid=True,
                            icon=helpers.get_icon(wf, 'package'))
        elif query and query.startswith('list'):
            for formula in filter_installed_casks(wf, query):
                wf.add_item(formula, 'Open homepage',
                            arg='brew cask home %s' % formula,
                            valid=True,
                            icon=helpers.get_icon(wf, 'package'))
        elif query and query.startswith('config'):
            edit_settings(wf)
            wf.add_item('`settings.json` has been opened.',
                        autocomplete='',
                        icon=helpers.get_icon(wf, 'info'))
        else:
            actions = cask_actions.ACTIONS
            # filter actions by query
            if query:
                actions = wf.filter(query, actions,
                                    key=helpers.search_key_for_action,
                                    match_on=MATCH_SUBSTRING)

            if len(actions) > 0:
                for action in actions:
                    wf.add_item(action['name'], action['description'],
                                uid=action['name'],
                                autocomplete=action['autocomplete'],
                                arg=action['arg'],
                                valid=action['valid'],
                                icon=helpers.get_icon(wf, 'chevron-right'))
            else:
                wf.add_item('No action found for "%s"' % query,
                            autocomplete='',
                            icon=helpers.get_icon(wf, 'info'))

        if len(wf._items) == 0:
            query_name = query[query.find(' ') + 1:]
            wf.add_item('No formula found for "%s"' % query_name,
                        autocomplete='%s ' % query[:query.find(' ')],
                        icon=helpers.get_icon(wf, 'info'))

    wf.send_feedback()

    # refresh cache
    cmd = ['/usr/bin/python', wf.workflowfile('cask_refresh.py')]
    run_in_background('cask_refresh', cmd)


if __name__ == '__main__':
    wf = Workflow(update_settings={'github_slug': GITHUB_SLUG})
    sys.exit(wf.run(main))
