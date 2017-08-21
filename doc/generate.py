#!/usr/bin/env python3

from __future__ import print_function

import ast
import docutils.core
import importlib
import inspect
import os
import sys


def public_modules():
    yield ('satori.rtm.__init__', [])
    yield ('satori.rtm.connection',
        ['Connection'])
    yield ('satori.rtm.client',
        ['Client', 'make_client'])
    yield ('satori.rtm.auth',
        ['RoleSecretAuthDelegate'])


def signature(module_name, class_name, fun_expr):
    m = importlib.import_module(module_name)
    fun = getattr(getattr(m, class_name), fun_expr.name)
    sig = inspect.signature(fun)
    return fun_expr.name + str(sig)


def rst_sections_in_module(tree, module_name, exports):
    docstring = ast.get_docstring(tree)
    if docstring:
        yield docstring
    for toplevel in tree.body:
        try:
            if toplevel.name not in exports:
                continue
        except AttributeError:
            continue

        print(
            'Documenting {}.{}'.format(module_name, toplevel.name),
            file=sys.stderr)
        class_doc = ast.get_docstring(toplevel)
        if class_doc:
            yield toplevel.name + '\n' + '-' * len(toplevel.name)
            yield class_doc
            if type(toplevel) == ast.ClassDef:
                for fun in toplevel.body:
                    if type(fun) != ast.FunctionDef:
                        continue
                    fun_doc = ast.get_docstring(fun)
                    if fun_doc:
                        fun_sig = signature(module_name, toplevel.name, fun)
                        yield fun.name + '\n' + '+' * len(fun.name)
                        yield 'Signature:\n    ' + fun_sig
                        yield fun_doc
                    else:
                        if not fun.name.startswith('_'):
                            print('Missing docstring for ' + fun.name, file=sys.stderr)


def rst_sections(sdkroot):
    for m, exports in public_modules():
        filename = os.path.join(sdkroot, *m.split('.')) + '.py'
        with open(filename) as fi:
            tree = ast.parse(fi.read(), filename)
            for section in rst_sections_in_module(tree, m, exports):
                yield section


def rst_to_html(rst):
    html = '<link rel="stylesheet" type="text/css" href="python_sdk_reference.css"/>\n'
    html += docutils.core.publish_parts(rst, writer_name='html')['html_body']
    return html


def main():
    sdkroot = os.path.realpath(sys.argv[1])
    whole_rst = '\n\n'.join(rst_sections(sdkroot))
    print(rst_to_html(whole_rst))


if __name__ == '__main__':
    main()