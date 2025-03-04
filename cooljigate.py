# coding=utf8
# -----------------------------------------------------------------------------
# Darkstorm Library
# Copyright (C) 2018 Martin Slater
# Created : Friday, 11 May 2018 10:11:57 AM
# -----------------------------------------------------------------------------
""" Looks up a verb in cooljigator and creates a file suitable for importing
into Ankidroid with all forms """

import argparse
import os
# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
import sys
import tempfile
from io import StringIO
from urllib.request import quote, urlopen

from bs4 import BeautifulSoup

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

IMPERFECTIVE_TEXT = "Expresses incomplete action."
PERFECTIVE_TEXT = "Expresses complete action."
MEANING_STR = "This verb can also mean the following: "
PERFECTIVE_COUNTERPART_STR = "This verb's perfective counterparts: "

ASPECT_UNKNOWN = 0
ASPECT_PERFECT = 1
ASPECT_IMPERFECT = 2

FORM_UNKNOWN = 0
FORM_I = 1
FORM_HE = 2
FORM_WE = 3
FORM_THEY = 5
FORM_MASC = 6
FORM_FEM = 7
FORM_PLURAL = 8
FORM_NEUTER = 9
FORM_YOU = 10

TENSER_UNKNOWN = 0
TENSE_PRESENT = 1
TENSE_PAST = 2
TENSE_FUTURE = 3
TENSE_IMPERATIVE = 4
TENSE_CONDITIONAL = 5

PAST_TENSE_FORMS = {
    FORM_MASC: 'past_singM',
    FORM_FEM: 'past_singF',
    FORM_NEUTER: 'past_singN',
    FORM_PLURAL: 'past_plur'
}

PRESENT_TENSE_FORMS = {
    FORM_I: 'present1',
    FORM_YOU: 'present2',
    FORM_HE: 'present3',
    FORM_WE: 'present4',
    FORM_PLURAL: 'present5',
    FORM_THEY: 'present6'
}

FUTURE_TENSE_FORMS = {
    FORM_I: 'future1',
    FORM_YOU: 'future2',
    FORM_HE: 'future3',
    FORM_WE: 'future4',
    FORM_PLURAL: 'future5',
    FORM_THEY: 'future6'
}

ALT_FUTURE_TENSE_FORMS = {
    FORM_I: 'p1',
    FORM_YOU: 'p2',
    FORM_HE: 'p3',
    FORM_WE: 'p4',
    FORM_PLURAL: 'p5',
    FORM_THEY: 'p6'
}

CONDITIONAL_TENSE_FORMS = {
    FORM_MASC: 'conditional_singM',
    FORM_FEM: 'conditional_singF',
    FORM_NEUTER: 'conditional_singN',
    FORM_PLURAL: 'conditional_plur'
}

IMPERATIVE_TENSE_FORMS = {
    FORM_YOU: 'imperative2',
    FORM_PLURAL: 'imperative5'
}

ALT_IMPERATIVE_TENSE_FORMS = {
    FORM_YOU: 'command2',
    FORM_PLURAL: 'command4'
}

ASPECT_POSTFIX = {
    ASPECT_IMPERFECT: 'нсв',
    ASPECT_PERFECT: 'св'
}

TENSE_POSTFIX = {
    TENSE_PRESENT: 'pres',
    TENSE_CONDITIONAL: 'cond',
    TENSE_FUTURE: 'future',
    TENSE_PAST: 'past',
    TENSE_IMPERATIVE: 'imp'
}

FORM_POSTFIX = {
    FORM_I: 'я',
    FORM_HE: 'он/она',
    FORM_YOU: 'ты',
    FORM_WE: 'мы',
    FORM_PLURAL: 'вы',
    FORM_THEY: 'они',
    FORM_FEM: 'она',
    FORM_MASC: 'он',
    FORM_NEUTER: 'оно'
}


# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

def make_fs_safe_name(filename):
    return "".join([c if c.isalpha() or c.isdigit() else '_' for c in filename]).strip()


def find_entry_by_id(soup, tense):
    elem = soup.find(id=tense)
    if elem is not None:
        en = elem.attrs['data-translated']
        if not en:
            en = elem.attrs['data=stressed']
        ru = elem.attrs['data-default']
        return Entry(en, ru)
    return None


def get_tense_entries(soup, forms):
    result = {}
    for key, val in forms.items():
        entry = find_entry_by_id(soup, val + '_no_accent')
        if not entry:
            entry = find_entry_by_id(soup, val)
        if entry:
            result[key] = entry
    return result

# -----------------------------------------------------------------------------
# Class
# -----------------------------------------------------------------------------


class Entry(object):
    def __init__(self, en, ru):
        self.ru = ru
        self.en = en


class Verb(object):
    def __init__(self, text):
        self.text = text
        self.aspect = ASPECT_UNKNOWN
        self.meanings = []
        self.present = None
        self.future = None
        self.past = None
        self.conditional = None
        self.imperative = None
        self.other_aspect_verbs = []

    def _get_tense_rows(self, stream, tense, entries, add_postfix, include_verb,  perf_verb, short_only):
        short = [FORM_I, FORM_HE, FORM_YOU, FORM_THEY, FORM_MASC, FORM_FEM]
        if entries is not None:
            rows = []
            perf_verb_tense = None
            if perf_verb is not None:
                perf_tense = tense
                if tense == TENSE_PRESENT:
                    perf_tense = TENSE_FUTURE
                perf_verb_tense = perf_verb.get_tense(perf_tense)

            for key, val in entries.items():
                if short_only and key not in short:
                    continue

                row = []
                form_postfix = ''
                if tense != TENSE_IMPERATIVE:
                    if key in FORM_POSTFIX:
                        form_postfix = FORM_POSTFIX[key] + ' '

                perf_val = ''
                if perf_verb_tense is not None and key in perf_verb_tense:
                    perf_val = perf_verb_tense[key].ru

                postfix = '%s|%s' % (
                    ASPECT_POSTFIX[self.aspect], TENSE_POSTFIX[tense])
                if tense == TENSE_IMPERATIVE:
                    postfix += '|%s' % ('formal' if key ==
                                        FORM_PLURAL else 'informal')

                if add_postfix:
                    postfix += '%s|%s' % (postfix, add_postfix)

                row.append(val.en)
                row.append(form_postfix)
                row.append(val.ru)
                row.append(perf_val)
                rows.append(row)

            return rows

    def _write_tense(self, stream, tense, entries, add_postfix, include_verb,  append_postfix, perf_verb, short_only):
        short = [FORM_I, FORM_HE, FORM_YOU, FORM_THEY, FORM_MASC, FORM_FEM]
        if entries is not None:
            perf_verb_tense = None
            if perf_verb is not None:
                perf_tense = tense
                if tense == TENSE_PRESENT:
                    perf_tense = TENSE_FUTURE
                perf_verb_tense = perf_verb.get_tense(perf_tense)

            for key, val in entries.items():
                if short_only and key not in short:
                    continue
                ru = ''
                if tense != TENSE_IMPERATIVE:
                    if key in FORM_POSTFIX:
                        ru += FORM_POSTFIX[key] + ' '

                ru += val.ru

                if perf_verb_tense is not None and key in perf_verb_tense:
                    ru += ' / %s' % (perf_verb_tense[key].ru)

                if not append_postfix:
                    stream.write('%s\n' % ru)
                else:
                    postfix = '%s|%s' % (
                        ASPECT_POSTFIX[self.aspect], TENSE_POSTFIX[tense])
                    if tense == TENSE_IMPERATIVE:
                        postfix += '|%s' % ('formal' if key ==
                                            FORM_PLURAL else 'informal')

                    if add_postfix:
                        postfix += '%s|%s' % (postfix, add_postfix)

                    en = '%s (%s)' % (val.en, postfix)

                    line = ''
                    if include_verb:
                        line = '%s (%s), ' % (
                            self.text, ASPECT_POSTFIX[self.aspect])
                    line += '%s, %s\n' % (en, ru)
                    stream.write(line)

        return len(entries) if entries else 0

    def get_filename(self):
        return make_fs_safe_name('to ' + '/'.join(self.meanings)) + '.txt'

    def get_tense(self, tense):
        all_tenses = {
            TENSE_PRESENT: self.present,
            TENSE_FUTURE: self.future,
            TENSE_PAST: self.past,
            TENSE_CONDITIONAL: self.conditional,
            TENSE_IMPERATIVE: self.imperative
        }
        return all_tenses[tense]

    def _format_string(self, str, style, doc_format):
        str = str.strip()
        if len(str) == 0:
            return ""
        if doc_format == "markdown":
            if style == "italic":
                return "_%s_" % (str)
            elif style == "bold":
                return "**%s**" % (str)
        elif doc_format == "html":
            if style == "italic":
                return "<i>%s</i>" % (str)
            elif style == "bold":
                return "<b>%s</b>" % (str)

        return str

    def _all_tenses(self):
        return [
            [TENSE_PRESENT, self.present],
            [TENSE_FUTURE, self.future],
            [TENSE_PAST, self.past],
            [TENSE_CONDITIONAL, self.conditional],
            [TENSE_IMPERATIVE, self.imperative]
        ]

    def write_markdown(self, stream, postfix, include_verb, append_postfix, perf_verb, short):
        HEADERS = [
            {
                "title": "English",
                "style": "italic",
                "align": "left"
            },
            {
                "title": "Form",
                "style": "bold",
                "align": "right"
            },
            {
                "title": "Imperfective",
                "style": "normal",
                "align": "left"
            },
            {
                "title": "Perfective",
                "style": "normal",
                "align": "left"
            }
        ]

        MARKDOWN_TABLE_COLUMN = {
            "left": "|:---",
            "center": "|:---:",
            "right": "|---:",
        }

        rows_to_print = [1, 2, 3]

        if append_postfix:
            rows_to_print = [0, 1, 2, 3]

        # header
        for row in rows_to_print:
            stream.write("|" + HEADERS[row]["title"])
        stream.write("|\n")
        for row in rows_to_print:
            stream.write(MARKDOWN_TABLE_COLUMN[HEADERS[row]["align"]])
        stream.write("|\n")

        for tense in self._all_tenses():
            rows = self._get_tense_rows(
                stream, tense[0], tense[1], postfix, include_verb,  perf_verb, short)
            if rows:
                for row in rows:
                    for row_idx in rows_to_print:
                        stream.write(
                            "|" + self._format_string(row[row_idx], HEADERS[row_idx]["style"], "markdown"))
                    stream.write("|\n")

    def write_plaintext(self, stream, postfix, include_verb, append_postfix, perf_verb, short):
        for tense in self._all_tenses():
            self._write_tense(
                stream, tense[0], tense[1], postfix, include_verb, append_postfix, perf_verb, short)


class Cooljigate(object):
    """ Cooljigate """
    CoolUrl = "http://cooljugator.com/ru"

    def __init__(self, args):
        """ Constructor """
        self.verb = args.verb
        self.conditionals = args.conditionals
        self.postfix = args.postfix or ''
        self.include_verb = args.include_verb
        self.write_to_disk = args.write_to_disk
        self.append_postfix = args.add_postfix
        self.print_header = args.print_header
        self.short = args.short
        self.single_aspect = args.single_aspect
        self.output_markdown = args.output_markdown or False

        self.output_format = "markdown" if self.output_markdown else "plaintext"

        if args.uni:
            if len(self.postfix):
                self.postfix += '|'
            self.postfix += 'uni'

        if args.multi:
            if len(self.postfix):
                self.postfix += '|'
            self.postfix += 'multi'

    def _get_document(self, verb):
        url = "%s/%s" % (Cooljigate.CoolUrl, quote(verb.lower()))
        # check if we have cached this file
        cache_name = os.path.join(
            tempfile.gettempdir(), make_fs_safe_name(url))
        if os.path.exists(cache_name):
            return open(cache_name, mode='r', encoding='utf-8').read()

        # update cache
        page = urlopen(url,)
        if page.url == 'https://cooljugator.com/404':
            return None
        response = page.read().decode('utf-8')
        open(cache_name, mode='w', encoding='utf-8').write(response)
        return response

    def run(self):
        verb = self.get_verb(self.verb)
        if verb is None:
            print("Verb not found")
            return
        other_aspect = None
        if not self.single_aspect and (len(verb.other_aspect_verbs) > 0):
            other_aspect = self.get_verb(verb.other_aspect_verbs[0])

        if other_aspect is not None:
            if verb.aspect == ASPECT_PERFECT:
                temp = verb
                verb = other_aspect
                other_aspect = temp

        self.print(verb, other_aspect)

    def get_verb(self, verb):
        text = self._get_document(verb)
        if text is None:
            return None
        soup = BeautifulSoup(text, "lxml")
        result = Verb(verb)

        # print('-----------------\n' + verb + "\n---------------------")
        # aspect
        imp = soup.find_all(attrs={"data-tooltip": IMPERFECTIVE_TEXT})
        if len(imp):
            result.aspect = ASPECT_IMPERFECT

            result.other = soup.find_all(
                attrs={"data-tooltip": IMPERFECTIVE_TEXT})
        else:
            perf = soup.find_all(attrs={"data-tooltip": PERFECTIVE_TEXT})
            if len(perf):
                result.aspect = ASPECT_PERFECT
            else:
                print('No aspect found')

        usage = soup.find(attrs={'id': 'usage-info'})

        # get verbs in the other aspect
        if usage is not None:
            other_aspect = usage.find_all('a')
            if other_aspect is not None:
                for link in other_aspect:
                    verb = link.get('href')
                    verb = verb[verb.rfind('/')+1:len(verb)]
                    if len(verb) > 0:
                        result.other_aspect_verbs.append(verb)

        # print(result.other_aspect_verbs)

        # meaning
        def_meaning = soup.find(id='mainform')
        if def_meaning:
            body = def_meaning.contents[0]
            result.meanings.append(body[body.find('(') + 1:body.rfind(')')])

        meaning = soup.find(attrs={'data-default': self.verb})
        if meaning is not None:
            body = meaning.contents[0]
            result.meanings.append(body[body.find('(') + 1:body.rfind(')')])

        # other meanings
        if usage.contents[0].startswith(MEANING_STR):
            result.meanings.extend(
                meaning.strip() for meaning in usage.contents[0][len(MEANING_STR):].split(','))

        # print(result.meanings)

        # past tense
        result.past = get_tense_entries(soup, PAST_TENSE_FORMS)
        result.present = get_tense_entries(soup, PRESENT_TENSE_FORMS)
        result.future = get_tense_entries(soup, FUTURE_TENSE_FORMS)
        if len(result.future) == 0:
            result.future = get_tense_entries(soup, ALT_FUTURE_TENSE_FORMS)
        result.imperative = get_tense_entries(soup, IMPERATIVE_TENSE_FORMS)
        if len(result.imperative) == 0:
            result.imperative = get_tense_entries(
                soup, ALT_IMPERATIVE_TENSE_FORMS)

        if self.conditionals:
            result.conditional = get_tense_entries(
                soup, CONDITIONAL_TENSE_FORMS)

        return result

    def print(self, imp_verb,  perf_verb):
        output = StringIO()

        if self.print_header:
            if perf_verb is not None:
                print("%s (imp, perf)" % (imp_verb.meanings[0]))
                print("%s / %s" % (imp_verb.text, perf_verb.text))
            print("")

        OUTPUT_FORMATS = {
            "plaintext": imp_verb.write_plaintext,
            "markdown": imp_verb.write_markdown
        }

        OUTPUT_FORMATS[self.output_format](output, self.postfix,
                                           self.include_verb, self.append_postfix, perf_verb, self.short)

        output = output.getvalue()
        sys.stdout.write(output)

        if self.write_to_disk:
            with open(self.get_filename(), mode='w', encoding='utf-8') as file:
                file.write(output)
                file.close()
        return 1


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    """ Main script entry point """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--conditionals',
                        help='Include conditional tenses',
                        dest='conditionals',
                        action='store_true')
    parser.add_argument('-p', '--postfix',
                        help='Additional text to add to the postfix section',
                        dest='postfix',
                        action='store')
    parser.add_argument('-s', '--add_postfix',
                        help='Print the english postfix section before the verb conjugation',
                        dest='add_postfix',
                        action='store_true')
    parser.add_argument('-u', '--uni',
                        help='Verb is a unidirectional verb',
                        dest='uni',
                        action='store_true')
    parser.add_argument('-r', '--header',
                        help='Print header containing english and russian verbs',
                        default='true',
                        dest='print_header',
                        action='store_true')
    parser.add_argument('-m', '--multi',
                        help='Verb is a multidirectional verb',
                        dest='multi',
                        action='store_true')
    parser.add_argument('-v', '--include-verb',
                        help='Include the verb in the output',
                        dest='include_verb',
                        action='store_true')
    parser.add_argument('-w', '--write',
                        help='Write the output to disk using an automatically generated name',
                        dest='write_to_disk',
                        action='store_true')
    parser.add_argument('-t', '--short',
                        help='Only output 1st, 2nd and 3rd person forms',
                        dest='short',
                        action='store_true')
    parser.add_argument('-o', '--only_verb',
                        help='Only output the verb and not the other aspect as well',
                        dest='single_aspect',
                        action='store_true')
    parser.add_argument('-d', '--markdown',
                        help='Output markdown',
                        dest='output_markdown',
                        action='store_true')

    parser.add_argument('verb', metavar='V', type=str,
                        help='Verb to conjugate')
    return Cooljigate(parser.parse_args()).run()


if __name__ == "__main__":
    main()
