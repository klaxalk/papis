"""
This command adds files to existing papis documents in some library.

For instance imagine you have two pdf files, ``a.pdf`` and ``b.pdf``
that you want to add to a document that matches with the query string
``einstein photon definition``, then you would use

::

    papis addto 'einstein photon definition' -f a.pdf -f b.pdf

notice that we repeat two times the flag ``-f``, this is important.

Cli
^^^
.. click:: papis.commands.addto:cli
    :prog: papis addto
"""
from string import ascii_lowercase
import os
import shutil
import papis.pick
import papis.utils
import papis.document
import papis.git
import papis.config
import papis.commands.add
import logging
import papis.cli
import click
import papis.strings

from typing import List, Optional


def run(
        document: papis.document.Document,
        link,
        copy_main,
        copy_pdf,
        filepaths: List[str],
        subfolder,
        git: bool = False) -> None:
    logger = logging.getLogger('addto')
    g = papis.utils.create_identifier(ascii_lowercase)
    string_append = ''

    _doc_folder = document.get_main_folder()
    if not _doc_folder:
        raise Exception("Document does not have a folder attached")

    for i in range(len(document.get_files())):
        string_append = next(g)

    new_file_list = []
    for i in range(len(filepaths)):
        in_file_path = filepaths[i]

        if not os.path.exists(in_file_path):
            raise Exception("{} not found".format(in_file_path))

        # Rename the file in the staging area
        new_filename = papis.utils.clean_document_name(
            papis.commands.add.get_file_name(
                papis.document.to_dict(document),
                in_file_path,
                suffix=string_append
            )
        )

        end_document_path = os.path.join(
            _doc_folder,
            new_filename
        )
        string_append = next(g)

        # Check if the absolute file path is > 255 characters
        if len(os.path.abspath(end_document_path)) >= 255:
            logger.warning(
                'Length of absolute path is > 255 characters. '
                'This may cause some issues with some pdf viewers'
            )

        if os.path.exists(end_document_path):
            logger.warning(
                "%s already exists, ignoring..." % end_document_path
            )
            continue

        in_file_abspath = os.path.abspath(in_file_path)

        if copy_pdf:
          pdfs_new_path = os.path.expanduser(os.path.join(
              papis.config.get_lib_dirs()[1], subfolder or '',  new_filename
          ))

          shutil.copy(in_file_path, pdfs_new_path)

          in_file_abspath = pdfs_new_path

          logger.debug(
                  "[CP] '%s' to '%s'" %
                  (in_file_abspath, end_document_path)
          )

        if copy_main:
            logger.debug(
                "[CP] '%s' to '%s'" %
                (in_file_path, end_document_path)
            )
            shutil.copy(in_file_path, end_document_path)

        if link:
            logger.debug(
                    "[SYMLINK] '%s' to '%s'" %
                    (in_file_abspath, end_document_path)
            )
            os.symlink(in_file_abspath, end_document_path)

        if link or copy_main:
            new_file_list.append(new_filename)
        else:
            new_file_list.append(in_file_abspath)

    if "files" not in document.keys():
        document["files"] = []
    document['files'] += new_file_list
    document.save()
    papis.database.get().update(document)
    if git:
        for r in new_file_list + [document.get_info_file()]:
            papis.git.add(_doc_folder, r)
        papis.git.commit(
            _doc_folder,
            "Add new files to '{}'".format(papis.document.describe(document)))


@click.command("addto")
@click.help_option('--help', '-h')
@papis.cli.query_option()
@papis.cli.git_option(help="Add and commit files")
@papis.cli.sort_option()
@click.option(
    "-f", "--files",
    help="File fullpaths to documents",
    multiple=True,
    type=click.Path(exists=True))

@click.option(
    "--link/--no-link",
    help="The file will be linked to the main folder instead of just saving its path",
    default=False
)

@click.option(
    "--copy-main/--no-copy-main",
    help="The file will be copied to the main folder",
    default=False
)

@click.option(
    "--copy-pdf/--no-copy-pdf",
    help="The file will be copied to the pdf folder",
    default=False
)

@click.option(
    "--file-name",
    help="File name for the document (papis format)",
    default=None
)

@click.option(
    "-d", "--subfolder",
    help="Subfolder in the library",
    default=""
)

@click.option(
    "--file-name",
    help="File name for the document (papis format)",
    default=None)
@papis.cli.doc_folder_option()
def cli(query: str,
        git: bool,
        files: List[str],
        link: bool,
        copy_main: bool,
        copy_pdf: bool,
        file_name: Optional[str],
        subfolder: bool,
        sort_field: Optional[str],
        doc_folder: str,
        sort_reverse: bool) -> None:
    """Add files to an existing document"""
    logger = logging.getLogger('cli:addto')

    if doc_folder:
        documents = [papis.document.from_folder(doc_folder)]
    else:
        documents = papis.database.get().query(query)

    if not documents:
        logger.warning(papis.strings.no_documents_retrieved_message)
        return

    document = papis.pick.pick_doc(documents)
    if not document:
        return

    if copy_pdf and copy_main:
        logger.warning(
            "--copy-pdf and --copy-main can't be used together"
        )
        return

    elif not copy_pdf and not copy_main:
        logger.warning(
            "--copy-pdf xor --copy-main has to be selected"
        )
        return

    if copy_main and link:
        logger.warning(
            "--copy-main and --link can't be used together"
        )
        return

    if copy_pdf and len(papis.config.get_lib_dirs()) <= 1:
        logger.warning(
            "the pdf directory no specified for --copy-pdf (e.g. dirs = [\"~/main_dir\", \"~/pdf_dir\"])"
        )
        return

    if sort_field:
        documents = papis.document.sort(documents, sort_field, sort_reverse)

    docs = papis.pick.pick_doc(documents)

    if not docs:
        return

    document = docs[0]

    if file_name is not None:  # Use args if set
        papis.config.set("add-file-name", file_name)

    run(document, link, copy_main, copy_pdf, files, subfolder, git=git)
