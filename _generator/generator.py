#!/usr/bin/python
# coding=utf-8

import argparse
import os
import sys

from enum import Enum
from html.parser import HTMLParser


class Stage(Enum):
    BEFORE_TITLE = 0
    TITLE = 1
    AFTER_TITLE_BEFORE_CONTENT = 2
    AFTER_CONTENT_BEFORE_FOOTER = 3
    FOOTER = 4
    AFTER_FOOTER = 5


class Parser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.stage = Stage.BEFORE_TITLE
        self.before_title_html = ""
        self.title_html = ""
        self.after_title_before_content_html = ""
        self.after_content_before_footer_html = ""
        self.footer_html = ""
        self.after_footer_html = ""

    def handle_starttag(self, tag, attrs):
        # Handle the title tag.
        if tag == "title":
            if self.title_html:
                sys.stdout.write("There's more than one title tags in the "
                                 "template! Exiting.\n")
                sys.exit(1)
            self.stage = Stage.TITLE
        # Handle the footer tag.
        if tag == "footer":
            if self.footer_html:
                sys.stdout.write("There's more than one foter tags in the "
                                 "template! Exiting.\n")
                sys.exit(1)
            self.stage = Stage.FOOTER

        change_to_after_content_stage = False
        self.__append_to_current_segment("<")
        self.__append_to_current_segment(tag)
        for pair in attrs:
            self.__append_to_current_segment(" ")
            self.__append_to_current_segment(pair[0])
            self.__append_to_current_segment("=")
            self.__append_to_current_segment("\"")
            self.__append_to_current_segment(pair[1])
            self.__append_to_current_segment("\"")
            # Handle the div#content tag.
            if tag == "div" and pair[0] == "id" and pair[1] == "content":
                change_to_after_content_stage = True
        self.__append_to_current_segment(">")
        if change_to_after_content_stage:
            self.stage = Stage.AFTER_CONTENT_BEFORE_FOOTER

    def handle_endtag(self, tag):
        self.__append_to_current_segment("</")
        self.__append_to_current_segment(tag)
        self.__append_to_current_segment(">")
        # Handle the title tag.
        if tag == "title":
            self.stage = Stage.AFTER_TITLE_BEFORE_CONTENT
        # Handle the footer tag.
        if tag == "footer":
            self.stage = Stage.AFTER_FOOTER

    def handle_startendtag(self, tag, attrs):
        self.__append_to_current_segment("<")
        self.__append_to_current_segment(tag)
        for pair in attrs:
            self.__append_to_current_segment(" ")
            self.__append_to_current_segment(pair[0])
            self.__append_to_current_segment("=")
            self.__append_to_current_segment("\"")
            self.__append_to_current_segment(pair[1])
            self.__append_to_current_segment("\"")
        self.__append_to_current_segment(" />")

    def handle_data(self, data):
        self.__append_to_current_segment(data)

    def handle_entityref(self, name):
        self.__append_to_current_segment("&")
        self.__append_to_current_segment(name)
        self.__append_to_current_segment(";")

    def handle_charref(self, name):
        self.__append_to_current_segment("&#")
        self.__append_to_current_segment(name)
        self.__append_to_current_segment(";")

    def handle_decl(self, decl):
        self.__append_to_current_segment("<!")
        self.__append_to_current_segment(decl)
        self.__append_to_current_segment(">")

    def __append_to_current_segment(self, s):
        if self.stage == Stage.BEFORE_TITLE:
            self.before_title_html += s
        elif self.stage == Stage.TITLE:
            self.title_html += s
        elif self.stage == Stage.AFTER_TITLE_BEFORE_CONTENT:
            self.after_title_before_content_html += s
        elif self.stage == Stage.AFTER_CONTENT_BEFORE_FOOTER:
            self.after_content_before_footer_html += s
        elif self.stage == Stage.FOOTER:
            self.footer_html += s
        elif self.stage == Stage.AFTER_FOOTER:
            self.after_footer_html += s
        else:
            sys.stdout.write("Got into a bad state. Exiting!\n")
            sys.exit(1)

class Stitcher(object):
    def __init__(self, template_html):
        self.parser = Parser()
        self.parser.feed(template_html)

    def stitched(self, content_html, generate_footer):
        content_html_lines = content_html.splitlines()
        title_html = self.parser.title_html

        # Clear lines before title.
        while content_html_lines and content_html_lines[0] == "":
            content_html_lines.pop(0)

        # Title.
        if content_html_lines:
            first_line = content_html_lines[0]
            if (first_line.startswith("<title>") and
                first_line.endswith("</title>")):
                title_html = content_html_lines.pop(0)
            elif first_line.startswith("<title>"):
                title_end_found = False
                while not title_end_found:
                    first_line = content_html_lines.pop(0)
                    if first_line.endswith("</title>"):
                        title_end_found = True
                    title_html += first_line

        # Clear lines in between title and content.
        while content_html_lines and content_html_lines[0] == "":
            content_html_lines.pop(0)

        # Content.
        indented_content_html_lines = ["        " + s
                                       for s
                                       in content_html_lines]
        indented_content_html = "\n".join(indented_content_html_lines)

        # Footer.
        footer_html = ""
        if generate_footer:
            footer_html = self.parser.footer_html

        # Actual stitch.
        return (self.parser.before_title_html +
                title_html +
                self.parser.after_title_before_content_html +
                "\n" +
                indented_content_html +
                self.parser.after_content_before_footer_html +
                footer_html +
                self.parser.after_footer_html)


class Generator(object):
    def __init__(self, relpaths):
        self.script_dir_path = os.path.dirname(os.path.abspath(__file__))
        self.content_dir_path = os.path.join(self.script_dir_path, "content")
        self.root_output_dir_path = os.path.split(self.script_dir_path)[0]

        self.paths = [os.path.abspath(relpath) for relpath in relpaths]
        if not self.paths:
            self.paths = [self.content_dir_path]

        template_html_path = os.path.join(self.script_dir_path,
                                             "template.html")
        template_html = self.__contents_of_file_path(template_html_path)
        if not template_html:
            sys.stdout.write("Couldn't load template.html!")
            sys.exit(1)
        self.stitcher = Stitcher(template_html)

    def generate(self):
        for path in self.paths:
            if os.path.isdir(path):
                for root, subdirs, files in os.walk(path):
                    for f in files:
                        file_path = os.path.join(root, f)
                        self.__generate_for_file(file_path)
            elif os.path.isfile(path):
                self.__generate_for_file(path)
            else:
                sys.stdout.write("Found a path that's neither a directory nor "
                                 "a file!")
                sys.exit(1)

    def __contents_of_file_path(self, file_path):
        contents = None
        with open(file_path) as fileobject:
            contents = fileobject.read()
            fileobject.close()
        return contents

    def ___write_contents_to_file_path(self, contents, file_path):
        with open(file_path, "w") as fileobject:
            fileobject.write(contents)
            fileobject.close()

    def __generate_for_file(self, file_path):
        if not file_path.startswith(self.content_dir_path):
            sys.stdout.write("The following file isn't in the "
                             "/_generator/content/ subtree, so skipping it: " +
                             file_path + "\n")
            return

        # Build output path.
        file_relpath_to_content_dir_path = os.path.relpath(file_path, self.content_dir_path)
        output_path = os.path.join(self.root_output_dir_path, file_relpath_to_content_dir_path)

        # Read contents of input path.
        file_content_html = self.__contents_of_file_path(file_path)
        if file_content_html:
            sys.stdout.write("Generating full HTML for " +
                             file_path +
                             " in " +
                             output_path +
                             "\n")
            generate_footer = True
            basename = os.path.basename(file_path)
            if basename == "index.html" or basename == "404.html":
                generate_footer = False
            # Stitch.
            stitched_html = self.stitcher.stitched(file_content_html, generate_footer)
            # Write contents to output path.
            self.___write_contents_to_file_path(stitched_html, output_path)
        else:
            sys.stdout.write("Couldn't load " + file_path + "! Skipping.\n")
            return



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generates full HTML pages by inserting content HTML "
                    "snippets into a template HTML file. The script can be ran "
                    "from anywhere in the file system, but all input HTML must "
                    "be in `.../_generator/content/` (where ... is the output "
                    "directory).")
    parser.add_argument("--version", "-v", action="version", version="1.0")
    parser.add_argument("relpaths", action="store", nargs="*",
                        help="All the file and directory paths to process. "
                             "Default is `.../_generator/content/`")
    args = parser.parse_args()
    g = Generator(args.relpaths).generate()
