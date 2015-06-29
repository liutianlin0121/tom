#!/usr/bin/env python
"""Doxygen XML to SWIG docstring converter.

Usage:

  doxy2swig.py [options] input.xml output.i

Converts Doxygen generated XML files into a file containing docstrings
that can be used by SWIG-1.3.x.  Note that you need to get SWIG
version > 1.3.23 or use Robin Dunn's docstring patch to be able to use
the resulting output.

input.xml is your doxygen generated XML file and output.i is where the
output will be written (the file will be clobbered).

"""
#
#
# This code is implemented using Mark Pilgrim's code as a guideline:
#   http://www.faqs.org/docs/diveintopython/kgp_divein.html
#
# Author: Prabhu Ramachandran
# License: BSD style
#
# Thanks:
#   Johan Hake:  the include_function_definition feature
#   Bill Spotz:  bug reports and testing.
#   Sebastian Henschel:   Misc. enhancements.
#   Michael Thon (June 2015): New features:
#      - docstrings for classes that contain constructor signatures and a
#        constructor and attributes section collecting the respective docs
#        (this is the place for these docs in python)
#        NOTE: As of June 2015 these do not show when using the -builtin
#              feature of swig (swig bug!)
#      - collect all documentation for overloaded functions into the python
#        function documentation
#      - rewrite of the text-wrapping.
#      - Attempt to produce docstrings that render nicely as markdown. This can
#        be improved once python tools actually support this.
#

from xml.dom import minidom
import re
import textwrap
import sys
import os.path
import optparse


def my_open_read(source):
    if hasattr(source, "read"):
        return source
    else:
        return open(source)


def my_open_write(dest):
    if hasattr(dest, "write"):
        return dest
    else:
        return open(dest, 'w')

# MARK: Text handling:
def shift(txt, indent, prepend = ''):
    """Return a list corresponding to the lines of text in the `txt` list
    indented by `indent` spaces. Prepend the string given in `prepend` to the
    beginning of the first line. Note that if len(prepend) > indent, then
    `prepend` will be truncated (doing better is tricky!). This preserves a 
    special '' entry at the end of `txt` (see `do_para` for the meaning).
    """
    special_end = txt[-1:] == ['']
    lines = ''.join(txt).splitlines(True)
    for i in range(1,len(lines)):
        if lines[i].strip():
            lines[i] = indent * ' ' + lines[i]
    if not lines:
        return prepend
    prepend = prepend[:indent]
    prepend = prepend + (indent - len(prepend)) * ' '
    lines[0] = prepend + lines[0]
    ret = [''.join(lines)]
    if special_end:
        ret.append('')
    return ret

class Doxy2SWIG:
    """Converts Doxygen generated XML files into a file containing
    docstrings that can be used by SWIG-1.3.x that have support for
    feature("docstring").  Once the data is parsed it is stored in
    self.pieces.

    """

    def __init__(self, src, include_function_definition=True, quiet=False,
                 width=80):
        """Initialize the instance given a source object.  `src` can
        be a file or filename.  If you do not want to include function
        definitions from doxygen then set
        `include_function_definition` to `False`.  This is handy since
        this allows you to use the swig generated function definition
        using %feature("autodoc", [0,1]).

        """
        f = my_open_read(src)
        self.my_dir = os.path.dirname(f.name)
        self.xmldoc = minidom.parse(f).documentElement
        f.close()

        self.pieces = []
        self.pieces.append('\n// File: %s\n' %
                           os.path.basename(f.name))

        self.space_re = re.compile(r'\s+')
        self.lead_spc = re.compile(r'^(%feature\S+\s+\S+\s*?)"\s+(\S)')
        self.multi = 0
        self.ignores = ['inheritancegraph', 'param', 'listofallmembers',
                        'innerclass', 'name', 'declname', 'incdepgraph',
                        'invincdepgraph', 'programlisting', 'type',
                        'references', 'referencedby', 'location',
                        'collaborationgraph', 'reimplements',
                        'reimplementedby', 'derivedcompoundref',
                        'basecompoundref', 'argsstring', 'exceptions']
        #self.generics = []
        self.include_function_definition = include_function_definition
        self.quiet = quiet
        self.textwidth = width
        self.indent = 0
        self.listitem = ''

    def generate(self):
        """Parses the file set in the initialization.  The resulting
        data is stored in `self.pieces`.

        """
        self.parse(self.xmldoc)

    def parse(self, node):
        """Parse a given node.  This function in turn calls the
        `parse_<nodeType>` functions which handle the respective
        nodes.

        """
        pm = getattr(self, "parse_%s" % node.__class__.__name__)
        pm(node)

    def parse_Document(self, node):
        self.parse(node.documentElement)

    def parse_Text(self, node):
        txt = node.data
        txt = txt.replace('\\', r'\\')
        txt = txt.replace('"', r'\"')
        # ignore pure whitespace
        m = self.space_re.match(txt)
        if m and len(m.group()) == len(txt):
            pass
        else:
            self.add_text(txt)

    def parse_Comment(self, node):
        """Parse a `COMMENT_NODE`.  This does nothing for now."""
        return

    def parse_Element(self, node):
        """Parse an `ELEMENT_NODE`.  This calls specific
        `do_<tagName>` handers for different elements.  If no handler
        is available the `subnode_parse` method is called.  All
        tagNames specified in `self.ignores` are simply ignored.

        """
        name = node.tagName
        ignores = self.ignores
        if name in ignores:
            return
        attr = "do_%s" % name
        if hasattr(self, attr):
            handlerMethod = getattr(self, attr)
            handlerMethod(node)
        else:
            self.subnode_parse(node)
            #if name not in self.generics: self.generics.append(name)

# MARK: Special format parsing
    def subnode_parse(self, node, pieces=None, indent=0, ignore=[], restrict=None):
        """Parse the subnodes of a given node. Subnodes with tags in the
        `ignore` list are ignored. If pieces is given, use this as target for
        the parse results instead of self.pieces. Indent all lines by the amount
        given in `indent`. Note that the inital content in `pieces` is not 
        indented. The final result is in any case added to self.pieces."""
        if pieces is not None:
            old_pieces, self.pieces = self.pieces, pieces
        else:
            old_pieces = []
        if indent > 0:
            pieces = ''.join(self.pieces)
            i_piece = pieces[:indent]
            if self.pieces[-1:] == ['']:
                self.pieces = [pieces[indent:]] + ['']
            elif self.pieces != []:
                self.pieces = [pieces[indent:]]
        self.indent += indent
        for n in node.childNodes:
            if restrict is not None:
                if n.nodeType != n.ELEMENT_NODE or n.tagName not in restrict:
                    continue
            if n.nodeType != n.ELEMENT_NODE or n.tagName not in ignore:
                self.parse(n)
        if indent > 0:
            self.pieces = shift(self.pieces, indent, i_piece)
        self.indent -= indent
        old_pieces.extend(self.pieces)
        self.pieces = old_pieces

    def surround_parse(self, node, pre_char, post_char):
        """Parse the subnodes of a given node. Subnodes with tags in the
        `ignore` list are ignored. Prepend `pre_char` and append `post_char` to
        the output in self.pieces."""
        self.add_text(pre_char)
        self.subnode_parse(node)
        self.add_text(post_char)
    
# MARK: Helper functions
    def get_specific_subnodes(self, node, name, recursive=0):
        """Given a node and a name, return a list of child `ELEMENT_NODEs`, that
        have a `tagName` matching the `name`. Search recursively for `recursive`
        levels.
        """
        children = [x for x in node.childNodes if x.nodeType == x.ELEMENT_NODE]
        ret = [x for x in children if x.tagName == name]
        if recursive > 0:
            for x in children:
                ret.extend(self.get_specific_subnodes(x, name, recursive-1))
        return ret

    def get_specific_nodes(self, node, names):
        """Given a node and a sequence of strings in `names`, return a
        dictionary containing the names as keys and child
        `ELEMENT_NODEs`, that have a `tagName` equal to the name.

        """
        nodes = [(x.tagName, x) for x in node.childNodes
                 if x.nodeType == x.ELEMENT_NODE and
                 x.tagName in names]
        return dict(nodes)

    def add_text(self, value):
        """Adds text corresponding to `value` into `self.pieces`."""
        if isinstance(value, (list, tuple)):
            self.pieces.extend(value)
        else:
            self.pieces.append(value)

    def get_Text(self, node):
        """Return the text stored in the firstChild.data of the `node`."""
        try:
            txt = node.firstChild.data
            txt = txt.replace('\\', r'\\')
            txt = txt.replace('"', r'\"')
            m = self.space_re.match(txt)
            if m and len(m.group()) == len(txt):
                return ''
            else:
                return txt
        except:
            return ''

    def add_line_with_subsequent_indent(self, value, indent=4):
        """Add line of text and wrap such that subsequent lines are indented
        by `indent` spaces.
        """
        if isinstance(value, (list, tuple)):
            line = ''.join(value)
        else:
            line = value
        line = line.strip()
        width = self.textwidth-self.indent-indent
        wrapped_lines = textwrap.wrap(line[indent:], width=width)
        for i in range(len(wrapped_lines)):
            if wrapped_lines[i] != '':
                wrapped_lines[i] = indent * ' ' + wrapped_lines[i]
        self.pieces.append(line[:indent] + '\n'.join(wrapped_lines)[indent:] + '  \n')

    def get_type(self, node):
        """Return the text represented by the child node with tag `type`."""
        pieces, self.pieces = self.pieces, []
        type = self.get_specific_subnodes(node, 'type')
        if type:
            self.subnode_parse(type[0])
        type_str = ''.join(self.pieces)
        self.pieces = pieces
        return type_str

    def get_function_definition(self, node):
        """Returns the function definition string for memberdef nodes."""
        name = self.get_Text(self.get_specific_subnodes(node, 'name')[0])
        argsstring = self.get_specific_subnodes(node, 'argsstring')
        try:
            argsstring = self.get_Text(argsstring[0])
        except:
            argsstring = ''
        type = self.get_type(node)
        function_definition = '`' + name + argsstring
        if type != '' and type != 'void':
            function_definition = function_definition + ' -> ' + type + '`'
        else:
            function_definition = function_definition + '`'
        return function_definition

# MARK: Special parsing tasks (need to be called manually)
    def make_constructor_list(self, constructor_nodes, classname):
        """Produces the "Constructors" section and the constructor signatures
        (since swig does not do so for classes) for class docstrings."""
        if constructor_nodes == []:
            return
        self.add_text(['\n', 'Constructors',
                       '\n', '------------'])
        for n in constructor_nodes:
            defn_str = classname
            argsstring = self.get_specific_subnodes(n, 'argsstring')
            if argsstring:
                defn_str = '`' + defn_str + self.get_Text(argsstring[0]) + '`'
            self.add_text('\n')
            self.add_line_with_subsequent_indent('* ' + defn_str)
            self.subnode_parse(n, pieces = [], indent=4, ignore=['definition', 'name'])

    def make_attribute_list(self, node):
        """Produces the "Attributes" section in class docstrings for public
        member variables (attributes).
        """
        atr_nodes = []
        for n in self.get_specific_subnodes(node, 'memberdef', recursive=2):
            if n.attributes['kind'].value == 'variable' and n.attributes['prot'].value == 'public':
                atr_nodes.append(n)
        if not atr_nodes:
            return
        self.add_text(['\n', 'Attributes',
                       '\n', '----------'])
        for n in atr_nodes:
            name = self.get_Text(self.get_specific_subnodes(n, 'name')[0])
            self.add_text(['\n* ', '`', name, '`', ' : '])
            self.add_text(['`', self.get_type(n), '`'])
            self.add_text('  \n')
            restrict = ['briefdescription', 'detaileddescription']
            self.subnode_parse(n, pieces=[''], indent=4, restrict=restrict)

    def get_memberdef_nodes_and_signatures(self, node, kind):
        """Collects the memberdef nodes and corresponding signatures that
        correspond to public function entries that are at most depth 2 deeper
        than the current (compounddef) node. Returns a dictionary with 
        function signatures (what swig expects after the %feature directive)
        as keys, and a list of corresponding memberdef nodes as values."""
        sig_dict = {}
        sig_prefix = ''
        if kind in ('file', 'namespace'):
            ns_node = node.getElementsByTagName('innernamespace')
            if not ns_node and kind == 'namespace':
                ns_node = node.getElementsByTagName('compoundname')
            if ns_node:
                sig_prefix = self.get_Text(ns_node[0]) + '::'
        elif kind in ('class', 'struct'):
            # Get the full function name.
            cn_node = node.getElementsByTagName('compoundname')
            sig_prefix = self.get_Text(cn_node[0]) + '::'

        md_nodes = self.get_specific_subnodes(node, 'memberdef', recursive=2)
        for n in md_nodes:
            if n.attributes['prot'].value != 'public':
                continue
            if n.attributes['kind'].value in ['variable', 'typedef']:
                continue
            if not self.get_specific_subnodes(n, 'definition'):
                continue
            name = self.get_Text(self.get_specific_subnodes(n, 'name')[0])
            if name[:8] == 'operator':
                continue
            sig = sig_prefix + name
            if sig in sig_dict:
                sig_dict[sig].append(n)
            else:
                sig_dict[sig] = [n]
        return sig_dict
            
    def handle_overloaded_memberdef(self, signature, memberdef_nodes):
        """Produces docstring entries containing an "Overloaded function"
        section with the documentation for each overload, if the function is
        overloaded. Else, produce normal documentation.
        """
        is_overloaded = len(memberdef_nodes) > 1
        self.add_text(['\n', '%feature("docstring") ', signature, ' "', '\n'])
        if self.include_function_definition:
            for n in memberdef_nodes:
                self.add_line_with_subsequent_indent(self.get_function_definition(n))
        if is_overloaded:
            self.add_text('\n')
            self.add_text(['Overloaded function', '\n',
                           '-------------------'])
            for n in memberdef_nodes:
                self.add_text('\n')
                self.add_line_with_subsequent_indent('* ' + self.get_function_definition(n))
                self.subnode_parse(n, pieces=[], indent=4, ignore=['definition', 'name'])
        else:
            for n in memberdef_nodes:
                self.subnode_parse(n, pieces=[], ignore=['definition', 'name'])
        self.add_text(['";', '\n'])

# MARK: Tag handlers
    def do_linebreak(self, node):
        self.add_text('  ')
    
    def do_emphasis(self, node):
        self.surround_parse(node, '_', '_')

    def do_bold(self, node):
        self.surround_parse(node, '**', '**')
    
    def do_computeroutput(self, node):
        self.surround_parse(node, '`', '`')

    def do_heading(self, node):
        pieces, self.pieces = self.pieces, []
        level = int(node.attributes['level'].value)
        self.subnode_parse(node)
        if level == 1:
            # self.pieces.insert(0,'\n')
            self.add_text(['\n', len(''.join(self.pieces).strip()) * '='])
        elif level == 2:
            self.add_text(['\n', len(''.join(self.pieces).strip()) * '-'])
        elif level >= 3:
            self.pieces.insert(0, level * '#' + ' ')
        self.add_text(['\n', ''])
        pieces.extend(self.pieces)
        self.pieces = pieces
            
    def do_includes(self, node):
        self.add_text('\nC++ includes: ')
        self.subnode_parse(node)
        self.add_text('\n')


# MARK: Para tag handler
    def do_para(self, node):
        """This is the only place where text wrapping is automatically performed.
        Generally, this function parses the node (locally), wraps the text, and
        then adds the result to self.pieces. However, it may be convenient to
        allow the previous content of self.pieces to be included in the text
        wrapping. For this, use the following *convention*:
        If self.pieces ends with '', treat it as part of the current paragraph.
        Else, insert new-line and start a new paragraph and "wrapping context".
        """
        if self.pieces[-1:] == ['']:
            pieces = []
        else:
            self.add_text('\n')
            pieces, self.pieces = self.pieces, []
        self.subnode_parse(node)
        dont_end_paragraph = self.pieces[-1:] == ['']
        # Now do the text wrapping:
        width = self.textwidth - self.indent
        wrapped_para = []
        for line in ''.join(self.pieces).splitlines():
            keep_markdown_newline = line[-2:] == '  '
            w_line = textwrap.wrap(line, width=width, break_long_words=False)
            if w_line == []:
                w_line = ['']
            if keep_markdown_newline:
                w_line[-1] = w_line[-1] + '  '
            for wl in w_line:
                wrapped_para.extend([wl, '\n'])
        if dont_end_paragraph:
            wrapped_para = wrapped_para[:-1] + ['']
        else:
            wrapped_para = wrapped_para[:-1] + ['  \n']
        pieces.extend(wrapped_para)
        self.pieces = pieces

# MARK: List tag handlers
    def do_itemizedlist(self, node):
        if self.pieces != []:
            self.add_text('\n')
        listitem = self.listitem
        if self.listitem == '':
            self.listitem = '*'
        else:
            self.listitem = '-'
        self.subnode_parse(node)
        self.listitem = listitem

    def do_orderedlist(self, node):
        if self.pieces != []:
            self.add_text('\n')
        listitem = self.listitem
        self.listitem = 0
        self.subnode_parse(node)
        self.listitem = listitem

    def do_listitem(self, node):
        try:
            self.listitem = int(self.listitem) + 1
            item = str(self.listitem) + '. '
        except:
            item = str(self.listitem) + ' '
        self.subnode_parse(node, item, indent=len(item))

# MARK: Parameter list tag handlers
    def do_parameterlist(self, node):
        if self.pieces != []: # We are not in a new para tag
            self.add_text(['  \n', '\n'])
        text = 'unknown'
        for key, val in node.attributes.items():
            if key == 'kind':
                if val == 'param':
                    text = 'Parameters'
                elif val == 'exception':
                    text = 'Exceptions'
                elif val == 'retval':
                    text = 'Returns'
                else:
                    text = val
                break
        if self.indent == 0:
            self.add_text([text, '\n', len(text) * '-', '\n'])
        else:
            self.add_text([text, ':  \n'])
        self.subnode_parse(node)

    def do_parameteritem(self, node):
        self.subnode_parse(node, pieces=['* ', ''])

    def do_parameternamelist(self, node):
        self.subnode_parse(node)
        self.add_text([' :', '  \n'])
    
    def do_parametername(self, node):
        if self.pieces != [] and self.pieces != ['* ', '']:
            self.add_text(', ')
        try:
            data = self.get_Text(node)
        except AttributeError:  # perhaps a <ref> tag in it
            data = self.get_Text(node.firstChild)
        self.add_text(['`', data, '`'])

    def do_parameterdescription(self, node):
        self.subnode_parse(node, pieces=[''], indent=4)

# MARK: %feature("docstring") producing tag handlers
    def do_compounddef(self, node):
        """This produces %feature("docstring") entries for classes, and handles
        class, namespace and file memberdef entries specially to allow for 
        overloaded functions. For other cases, passes parsing on to standard
        handlers (which may produce unexpected results).
        """
        kind = node.attributes['kind'].value
        if kind in ('class', 'struct'):
            prot = node.attributes['prot'].value
            if prot != 'public':
                return
            defn_n = self.get_specific_subnodes(node, 'compoundname')
            self.add_text('\n\n')
            classdefn = self.get_Text(defn_n[0])
            classname = classdefn.split('::')[-1]
            self.add_text('%%feature("docstring") %s "\n' % classdefn)
            constructor_nodes = []
            for n in self.get_specific_subnodes(node, 'memberdef', recursive=2):
                if n.attributes['prot'].value == 'public':
                    defn = self.get_specific_subnodes(n, 'definition')
                    if defn and self.get_Text(defn[0]) == classdefn + '::' + classname:
                        constructor_nodes.append(n)
            for n in constructor_nodes:
                defn_str = classname
                argsstring = self.get_specific_subnodes(n, 'argsstring')
                if argsstring:
                    defn_str = defn_str + self.get_Text(argsstring[0])
                self.add_line_with_subsequent_indent(['`', defn_str,'`'])

            names = ('briefdescription','detaileddescription')
            sub_dict = self.get_specific_nodes(node, names)
            for n in ('briefdescription','detaileddescription'):
                if n in sub_dict:
                    self.parse(sub_dict[n])

            self.make_constructor_list(constructor_nodes, classname)
            self.make_attribute_list(node)

            sub_list = self.get_specific_subnodes(node, 'includes')
            if sub_list:
                self.parse(sub_list[0])
            self.add_text(['";', '\n'])

            names = ['compoundname', 'briefdescription','detaileddescription', 'includes']
            self.subnode_parse(node, ignore = names)

        elif kind in ('file', 'namespace'):
            nodes = node.getElementsByTagName('sectiondef')
            for n in nodes:
                self.parse(n)

        # now handle possibly overloaded member functions Simply add additional
        # %feature("docstring") directives and rely on the fact that swig treats
        # later ones as overwriting previous ones.
        if kind in ['class', 'struct','file', 'namespace']:
            md_nodes = self.get_memberdef_nodes_and_signatures(node, kind)
            for sig in md_nodes:
                self.handle_overloaded_memberdef(sig, md_nodes[sig])
    
    def do_memberdef(self, node):
        """DEPRECATED! This should no longer be needed, since the according
        entries are produces by `handle_overloaded_memberfunction`. This is -- 
        and its produces entries -- are kept for now"""
        prot = node.attributes['prot'].value
        id = node.attributes['id'].value
        kind = node.attributes['kind'].value
        tmp = node.parentNode.parentNode.parentNode
        compdef = tmp.getElementsByTagName('compounddef')[0]
        cdef_kind = compdef.attributes['kind'].value

        if prot != 'public':
            return
        first = self.get_specific_nodes(node, ('definition', 'name'))
        name = self.get_Text(first['name'])
        if name[:8] == 'operator':  # Don't handle operators yet.
            return
        if not 'definition' in first or kind in ['variable', 'typedef']:
            return

        self.add_text('\n')
        self.add_text(['/* deprecated entry */', '\n'])
        self.add_text('%feature("docstring") ')

        anc = node.parentNode.parentNode
        if cdef_kind in ('file', 'namespace'):
            ns_node = anc.getElementsByTagName('innernamespace')
            if not ns_node and cdef_kind == 'namespace':
                ns_node = anc.getElementsByTagName('compoundname')
            if ns_node:
                ns = self.get_Text(ns_node[0])
                self.add_text(' %s::%s "\n' % (ns, name))
            else:
                self.add_text(' %s "\n' % (name))
        elif cdef_kind in ('class', 'struct'):
            # Get the full function name.
            anc_node = anc.getElementsByTagName('compoundname')
            cname = self.get_Text(anc_node[0])
            self.add_text(' %s::%s "\n' % (cname, name))

        if self.include_function_definition:
            self.add_line_with_subsequent_indent(self.get_function_definition(node))
            self.add_text('\n')
        self.add_text('')
        for n in node.childNodes:
            if n not in first.values():
                self.parse(n)
        self.add_text(['";', '\n'])

    def do_definition(self, node):
        """Can this ever be called??"""
        print("Warning: This should not have happened!")
        data = self.get_Text(node)
        self.add_text('%s "\n%s' % (data, data))

    def do_simplesect(self, node):
        kind = node.attributes['kind'].value
        if kind in ('date', 'rcs', 'version'):
            return
        if self.pieces != []:
            self.add_text('\n')
        if kind == 'warning':
            self.subnode_parse(node, pieces=['WARNING: ',''], indent=4)
        elif kind == 'see':
            self.subnode_parse(node, pieces=['See: ',''], indent=4)
        elif kind == 'return':
            if self.indent == 0:
                pieces = ['Returns', '\n', len('Returns') * '-', '\n', '']
            else:
                pieces = ['Returns:', '\n', '']
            self.subnode_parse(node, pieces=pieces)
        else:
            self.subnode_parse(node)

    def do_argsstring(self, node):
        self.subnode_parse(node)
        self.add_text('\n')

# MARK: Entry tag handlers (dont print anything meaningful)
    def do_sectiondef(self, node):
        kind = node.attributes['kind'].value
        if kind in ('public-func', 'func', 'user-defined', ''):
            self.subnode_parse(node)

    def do_header(self, node):
        """For a user defined section def a header field is present
        which should not be printed as such, so we comment it in the
        output."""
        data = self.get_Text(node)
        self.add_text('\n/*\n %s \n*/\n' % data)
        # If our immediate sibling is a 'description' node then we
        # should comment that out also and remove it from the parent
        # node's children.
        parent = node.parentNode
        idx = parent.childNodes.index(node)
        if len(parent.childNodes) >= idx + 2:
            nd = parent.childNodes[idx + 2]
            if nd.nodeName == 'description':
                nd = parent.removeChild(nd)
                self.add_text('\n/*')
                self.subnode_parse(nd)
                self.add_text('\n*/\n')

    def do_member(self, node):
        kind = node.attributes['kind'].value
        refid = node.attributes['refid'].value
        if kind == 'function' and refid[:9] == 'namespace':
            self.subnode_parse(node)

    def do_doxygenindex(self, node):
        self.multi = 1
        comps = node.getElementsByTagName('compound')
        for c in comps:
            refid = c.attributes['refid'].value
            fname = refid + '.xml'
            if not os.path.exists(fname):
                fname = os.path.join(self.my_dir,  fname)
            if not self.quiet:
                print("parsing file: %s" % fname)
            p = Doxy2SWIG(fname, self.include_function_definition, self.quiet,
                          self.textwidth)
            p.generate()
            self.pieces.extend(p.pieces)

    def write(self, fname):
        o = my_open_write(fname)
        o.write(''.join(self.pieces))
        o.write('\n')
        o.close()

def convert(input, output, include_function_definition=True, quiet=False,
            width=80):
    p = Doxy2SWIG(input, include_function_definition, quiet, width)
    p.generate()
    p.write(output)


def main():
    usage = __doc__
    parser = optparse.OptionParser(usage)
    parser.add_option("-n", '--no-function-definition',
                      action='store_true',
                      default=False,
                      dest='func_def',
                      help='do not include doxygen function definitions')
    parser.add_option("-q", '--quiet',
                      action='store_true',
                      default=False,
                      dest='quiet',
                      help='be quiet and minimize output')
    parser.add_option("-w", '--width', type="int",
                      action='store',
                      dest='width',
                      default=80,
                      help='textwidth for wrapping (default: 80)')

    options, args = parser.parse_args()
    if len(args) != 2:
        parser.error("error: no input and output specified")

    convert(args[0], args[1], not options.func_def, options.quiet,
            options.width)


if __name__ == '__main__':
    main()
