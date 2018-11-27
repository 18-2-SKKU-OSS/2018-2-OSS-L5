
import json
import os
import polib
import re
import ujson
from subprocess import CalledProcessError, check_output
from typing import Any, Dict, List

from django.conf import settings
from django.conf.locale import LANG_INFO
from django.core.management.base import CommandParser
from django.core.management.commands import compilemessages
from django.utils.translation.trans_real import to_language

from zerver.lib.i18n import with_language

class Command(compilemessages.Command):

    def add_arguments(self, parser: CommandParser) -> None:
        super().add_arguments(parser)

        parser.add_argument(
            '--strict', '-s',
            action='store_true',
            default=False,
            help='Stop execution in case of errors.')

    def handle(self, *args: Any, **options: Any) -> None:
        if settings.PRODUCTION:
            # HACK: When using upgrade-zulip-from-git, we're in a
            # production environment where STATIC_ROOT will include
            # past versions; this ensures we only process the current
            # version
            settings.STATIC_ROOT = os.path.join(settings.DEPLOY_ROOT, "static")
            settings.LOCALE_PATHS = (os.path.join(settings.DEPLOY_ROOT, 'static/locale'),)
        super().handle(*args, **options)
        self.strict = options['strict']
        self.extract_language_options()
        self.create_language_name_map()

    def create_language_name_map(self) -> None:
        join = os.path.join
        static_root = settings.STATIC_ROOT
        path = join(static_root, 'locale', 'language_options.json')
        output_path = join(static_root, 'locale', 'language_name_map.json')

        with open(path, 'r') as reader:
            languages = ujson.load(reader)
            lang_list = []
            for lang_info in languages['languages']:
                lang_info['name'] = lang_info['name_local']
                del lang_info['name_local']
                lang_list.append(lang_info)

            lang_list.sort(key=lambda lang: lang['name'])

        with open(output_path, 'w') as output_file:
            ujson.dump({'name_map': lang_list}, output_file, indent=4, sort_keys=True)
            output_file.write('\n')

    def get_po_filename(self, locale_path: str, locale: str) -> str:
        po_template = '{}/{}/LC_MESSAGES/django.po'
        return po_template.format(locale_path, locale)

    def get_json_filename(self, locale_path: str, locale: str) -> str:
        return "{}/{}/translations.json".format(locale_path, locale)

    def get_name_from_po_file(self, po_filename: str, locale: str) -> str:
        lang_name_re = re.compile(r'"Language-Team: (.*?) \(')
        with open(po_filename, 'r') as reader:
            result = lang_name_re.search(reader.read())
            if result:
                try:
                    return result.group(1)
                except Exception:
                    print("Problem in parsing {}".format(po_filename))
                    raise
            else:
                raise Exception("Unknown language %s" % (locale,))

    def get_locales(self) -> List[str]:
        tracked_files = check_output(['git', 'ls-files', 'static/locale'])
        tracked_files = tracked_files.decode().split()
        regex = re.compile(r'static/locale/(\w+)/LC_MESSAGES/django.po')
        locales = ['en']
        for tracked_file in tracked_files:
            matched = regex.search(tracked_file)
            if matched:
                locales.append(matched.group(1))

        return locales

    def extract_language_options(self) -> None:
        locale_path = "{}/locale".format(settings.STATIC_ROOT)
        output_path = "{}/language_options.json".format(locale_path)

        data = {'languages': []}  # type: Dict[str, List[Dict[str, Any]]]

        try:
            locales = self.get_locales()
        except CalledProcessError:
            # In case we are not under a Git repo, fallback to getting the
            # locales using listdir().
            locales = os.listdir(locale_path)
            locales.append('en')
            locales = list(set(locales))

        for locale in locales:
            if locale == 'en':
                data['languages'].append({
                    'name': 'English',
                    'name_local': 'English',
                    'code': 'en',
                    'locale': 'en',
                })
                continue

            lc_messages_path = os.path.join(locale_path, locale, 'LC_MESSAGES')
            if not os.path.exists(lc_messages_path):
                # Not a locale.
                continue

            info = {}  # type: Dict[str, Any]
            code = to_language(locale)
            percentage = self.get_translation_percentage(locale_path, locale)
            try:
                name = LANG_INFO[code]['name']
                name_local = LANG_INFO[code]['name_local']
            except KeyError:
                # Fallback to getting the name from PO file.
                filename = self.get_po_filename(locale_path, locale)
                name = self.get_name_from_po_file(filename, locale)
                name_local = with_language(name, code)

            info['name'] = name
            info['name_local'] = name_local
            info['code'] = code
            info['locale'] = locale
            info['percent_translated'] = percentage
            data['languages'].append(info)

        with open(output_path, 'w') as writer:
            json.dump(data, writer, indent=2, sort_keys=True)
            writer.write('\n')

    def get_translation_percentage(self, locale_path: str, locale: str) -> int:

        # backend stats
        po = polib.pofile(self.get_po_filename(locale_path, locale))
        not_translated = len(po.untranslated_entries())
        total = len(po.translated_entries()) + not_translated

        # frontend stats
        with open(self.get_json_filename(locale_path, locale)) as reader:
            for key, value in ujson.load(reader).items():
                total += 1
                if value == '':
                    not_translated += 1

        # mobile stats
        with open(os.path.join(locale_path, 'mobile_info.json')) as mob:
            mobile_info = ujson.load(mob)
        try:
            info = mobile_info[locale]
        except KeyError:
            if self.strict:
                raise
            info = {'total': 0, 'not_translated': 0}

        total += info['total']
        not_translated += info['not_translated']

        return (total - not_translated) * 100 // total
