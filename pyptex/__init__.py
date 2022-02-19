r"""
## PypTeX: the Python Preprocessor for TeX

### Author: Sébastien Loisel

PypTeX is the Python Preprocessor for LaTeX. It allows one to embed Python
code fragments in a LaTeX template file.

# Installation

`pip install pyptex`

1. You will also need a LaTeX installation, and the default LaTeX processor is `pdflatex`.
2. You need a Python 3 installation.

<img alt="An example plot with PypTeX" width="500" src="examples/brochure.png">

# Introduction

Assume `example.tex` contains the following text:

    \documentclass{article}
    @{from sympy import *}
    \begin{document}
    $$\int x^3\,dx = @{S('integrate(x^3,x)')}+C$$
    \end{document}

The command `pyptex example.tex` will generate `example.pdf`,
as well as the intermediary file `example.pyptex`. PypTeX works by extracting Python
fragments in `example.tex` indicated by either `@{...}` or `@{{{...}}}` and substituting the
corresponding outputs to produce `example.pyptex`, which is then compiled with
`pdflatex example.pyptex`, although one can use any desired LaTeX processor in lieu of
`pdflatex`. The intermediary file `example.pyptex` is pure LaTeX.

When processing Python fragments, the global scope contains an object `pyp` that is a
(weakref proxy for a) `pyptex.pyptex` object that makes available several helper functions
and useful data. For example, `pyp.print("hello, world")` inserts the string `hello, world`
into the generated `example.pyptex` file.

* The `pyptex` executable tries to locate the Python 3 executable using `/usr/bin/env python3`.
If this is causing you problems, try `python -u -m pyptex example.tex` instead.

# Slightly bigger examples

* 2d and 3d plotting [tex](examples/plots.tex)
|
[pdf](examples/plots.pdf)
* Matrix inverse exercise [tex](examples/matrixinverse.tex)
|
[pdf](examples/matrixinverse.pdf)
* The F19NB handout for numerical linear algebra at Heriot-Watt university is generated with PypTeX. [pdf](https://www.macs.hw.ac.uk/~sl398/notes.pdf)

# Plotting with `sympy` and `matplotlib`

PypTeX implements its own `matplotlib` backend, a thin wrapper around the built-in postscript backend.
The PypTeX backend takes care of generating `.eps` files and importing them into your document via
`\includegraphics`. In that scenario, you must do `\usepackage{graphicx}` in your LaTeX preamble.
The precise "includegraphics" command can be set, e.g. by
`pyp.includegraphics=r"\includegraphics[width=0.9\textwidth]"`.

To create a plot with `sympy`, one can do:
```python
sympy.plot(sympy.S('sin(x)+cos(pi*x)'))
```
At the end of each Python fragment `@{...}`, PypTeX saves each generated figure to a
`x.eps` file, and these figures are then inserted via `includegraphics` into the generated
`.tex` file. Once a figure has been auto-showed in this manner, it will not be
auto-showed again. The auto-show behavior can be disabled by setting `pyp.autoshow = False`.
Figures can also be displayed manually via `pyp.pp('{myfig})`.

```python
plt.plot([1,2,3],[2,1,4])
```

# Template preprocessing vs embedding

PypTeX is a template preprocessor for LaTeX based on the Python language. When Python
is embedded into LaTeX, Python code fragments are identified by LaTeX commands that use
standard TeX notation, such as `\py{...}`. The code extraction is performed by TeX, then
the code fragments are executed by Python, finally TeX is run again to merge the
Python-generated LaTeX fragments back into the master file.

By contrast, PypTeX is a preprocessor that extracts Python code fragments indicated by
`@{...}` using regular expressions. Once the relevant Python outputs are collected, they
are also inserted by regular expressions. LaTeX is only invoked once, on the final output.

There may be specialized cases where Python embeddings are preferred, but we found
that template preprocessing is superior to embedding. There are many reasons (that
will be described elsewhere in detail) but we briefly mention the following reasons:
1. Embeddings can result in deadlock. If we have `\includegraphics{dog.png}`, but
`dog.png` is generated by a Python fragment, the first run of LaTeX will fail because
`dog.png` does not yet exist. Since LaTeX failed, it did not extract the Python fragments
and we cannot run the Python code that would generate `dog.png` unless we temporarily
delete the `\includegraphics{dog.png}` from `a.tex`. In our experience, deadlock
occurs almost every time we edit our large `.tex` files.
2. Embedding makes debugging difficult. By contrast, PypTeX treats Python's debugger Pdb
as a first-class citizen and everything should work as normal. Please let us know if some
debugging task somehow fails for you.
3. Performance. Substituting using regular expressions is faster than running the
LaTeX processor.

# Pretty-printing template strings from Python with `pp`

The function ```pp(X)``` pretty-prints the template string `X` with substitutions
from the local scope of the caller. This is useful for medium length LaTeX fragments
containing a few Python substitutions:
```python
>>> from pyptex import pp
>>> from sympy import *
>>> p = S('x^2-2*x+3')
>>> dpdx = p.diff(S('x'))
>>> x0 = solve(dpdx)[0]
>>> pp('The minimum of $y=@p$ is at $x=@x0$.')
'The minimum of $y=x^{2} - 2 x + 3$ is at $x=1$.'
```

# Caching

When compiling `a.tex`, PypTeX creates a cache file `a.pickle`. This file is
automatically invalidated if the Python fragments in `a.tex` change, or if some
other dependencies have changed. Dependencies can be declared from inside `a.tex` via
`pyp.dep(...)`. Caching can be completely disabled with `pyp.disable_cache=True`,
and users can delete `a.pickle` as necessary.

# Scopes

For each template file `a.tex`, `b.tex`, ... a private global scope is created for
executing Python fragments. This means that Python fragments in `a.tex` cannot use
functions or variables defined in `b.tex`, although shared functions could be
implemented in a shared `c.py` Python module that is `import`ed into
`a.tex` and `b.tex`.

In particular, when does `pyp.input('b.tex')` from `a.tex`, the code in `b.tex` cannot
use functions and data generated in `a.tex`. This means that `b.tex` is effectively
a "compilation unit" whose semantics are essentially independent of `a.tex`.

For any given `a.tex` file, its private global scope is initialized with the
standard Python builtins and with a single `pyp` object, which is a `weakref.proxy`
to the `pyptex('a.tex')` instance. We use a `weakref.proxy` because the global
scope of `a.tex` is a `dict` stored in the (private) variable `pyp.__global__`. The
use of `weakref.proxy` avoids creating a circular data structure that would otherwise
stymie the Python garbage collector. For most purposes, this global `pyp` variable
acts exactly like a concrete `pyptex` instance.

# TeXShop

If you want to use TeXShop on Mac, put the following into `~/Library/TeXShop/Engines/pyptex.engine` and restart TeXShop:
```
#!/bin/bash
pyptex $1
```
"""

from contextlib import suppress
import datetime
import glob
import inspect
import os
import pickle
import re
import string
import subprocess
import sys
import time
import traceback
import weakref
import streamcapture
import numpy
import sympy
import types
import matplotlib
import matplotlib.pyplot
from pathlib import Path
from matplotlib.backend_bases import Gcf, FigureManagerBase
from matplotlib.backends.backend_ps import FigureCanvasPS

__pdoc__ = {
    'pyptex.compile': False,
    'pyptex.generateddir': False,
    'pyptex.process': False,
    'pyptex.resolvedeps': False,
    'pyptex.run': False,
    'FigureManager': False,
    'FigureManager.show': False,
}

__pdoc__['pyptexNameSpace'] = False
class pyptexNameSpace:
    def __init__(self,d):
        self.__dict__.update(d)
    def __str__(self):
        return fr'\input{{{self.pyp.pyptexfilename}}}'
    def __repr__(self):
        return repr(str(self))
    def __eq__(self, other):
        if isinstance(self, pyptexNameSpace) and isinstance(other, pyptexNameSpace):
           return self.__dict__ == other.__dict__
        return NotImplemented

######################################################################
# The stuff below makes pyptex into a matplotlib backend
FigureCanvas = FigureCanvasPS

class FigureManager(FigureManagerBase):
    def show(self, **kwargs):
        pass

__pdoc__['show'] = False
def show(*args, **kwargs):
    pass
# end of matplotlib backend
######################################################################

ppparser = re.compile(r"@([a-zA-Z_][a-zA-Z0-9_]*)|@{([^{}}]*)}",re.DOTALL)
pypparser = re.compile(r'((?<!\\)%[^\n]*\n)|(@@)|(@(\[([a-zA-Z]*)\])?{([^{}]+)}|@(\[([a-zA-Z]*)\])?{{{(.*?)}}})', re.DOTALL)
bibentryname = re.compile(r'[^{]*{([^,]*),', re.DOTALL)
stripext = re.compile(r'(.*?)(\.(pyp\.)?[^\.]*)?$', re.DOTALL)


__pdoc__['format_my_nanos'] = False
# Credit: abarnet on StackOverflow
def format_my_nanos(nanos: int):
    """Convert nanoseconds to a human-readable format"""
    dt = datetime.datetime.fromtimestamp(nanos / 1e9)
    return '{}.{:09.0f}'.format(dt.strftime('%Y-%m-%d@%H:%M:%S'), nanos % 1e9)


__pdoc__['dictdiff'] = False
def dictdiff(A, B):
    A = set(A.items())
    B = set(B.items())
    D = A ^ B
    if len(D) == 0:
        return None
    return next(iter(D))

class pyptex:
    r"""Class `pyptex.pyptex` is used to parse an input (templated) `a.tex` file
    and produce an output `a.pyptex` file, and can be used as follows:
        `pyp = pyptex('a.tex')`
    The constructor reads `a.tex`, executes Python fragments and performs relevant
    substitutions, writing `a.pyptex` to disk. The contents of `a.pyptex` are also
    available as `pyp.compiled`.
    """

    def genname(self, pattern: str = 'fig{gencount}.eps'):
        r"""Generate a filename

        To produce an automatically generated filename, use the statement
        `pyp.genname()`, where `pyp` is an object of type `pyptex`, for parsing a
        given file `a.tex`. By default, this will generate the name
        `'a-generated/fig{gencount}.eps'`.
        The subdirectory can be overridden by overwriting `pyp.gendir`,
        and `gencount` denotes `pyp.gencount`. Any desired pattern can be used,
        for example:
            `name = pyp.genname('hello-{gencount}-{thing}.txt')`
        will return something like `'a-generated/hello-X-Y.txt'`, where
        `X` is `pyp.gencount` and `Y` is `pyp.thing`.

        `pyp.genname()` does not actually create the file. `pyp.genname()` increments
        `pyp.gencount` every time it is called.
        """
        self.gencount += 1
        return f'{self.gendir}/{pattern.format(**self.__dict__)}'

    def __setupfig__(self, fig):
        if not hasattr(fig,'__FIGNAME__'):
            figname = self.genname()
            Path(figname).touch()
            self.dep(figname)
            fig.__FIGNAME__ = figname
        if not hasattr(fig,'__IG__'):
            fig.__IG__ = (self.includegraphics%figname)
        if not hasattr(fig,'drawn'):
            fig.drawn = False
        return fig.__IG__
    def showall(self):
        for num, figmanager in enumerate(Gcf.get_all_fig_managers()):
            fig = figmanager.canvas.figure
            self.__setupfig__(fig)
            if fig.drawn:
                pass
            else:
                self.print(fig)

    def generateddir(self):
        """This is an internal function that creates the generated directory."""
        self.gendir = f'{self.filename}-generated'
        if not os.path.exists(self.gendir):
            os.makedirs(self.gendir)
        self.gencount = 0
    def freeze(self):
        """'Freezes' the global scope of the caller by performing a shallow copy and copying it to 
        `pyp.__frozen__`

        See also `pyptex.clear()`"""
        self.__frozen__ = inspect.stack()[1][0].f_globals.copy()
    def clear(self):
        """Clears all global variable.

        pyptex.clear() clears all the global variables of the caller. Example usage:
        ```python
        a = 1
        print(a)      # this prints 1
        pyp.clear()
        print(a)      # this raises an exception because
                      # a is now undefined.
        ```
        
        The global scope is restored from the dictionary `pyp.__frozen__`, which initially only contains
        the pyp object and the `__builtins__` module. One can add more items to the `__frozen__` dict, e.g.
        by importing some standard module. For example,

        ```python
        my_variable = 78
        import sys
        pyp.freeze()     # This freezes my_variable and sys.
        foo = 1          # Now foo is defined...
        pyp.clear()
        # ...Now foo is undefined, but my_variable is still 78,
        # and the sys module is still available.
        ```

        Note that `pyp.freeze()` performs a shallow copy, so:
        ```python
        a = [1,2,3]
        pyp.freeze()  # a = [1,2,3] is now in the frozen scope.
        a[1] = 7      # Now a = [1,7,3] in the global scope.
        pyp.clear()
        # Still a = [1,7,3] because the scope copy was shallow.
        ```
        """
        foo = self.__frozen__
        bar = inspect.stack()[1][0].f_globals
        for k,v in foo.items():
            bar[k] = v
        kk = list(bar.keys())
        for k in kk:
            if k not in foo:
                del bar[k]

    def __init__(self, texfilename, argv=None, latexcommand=False):
        r"""`pyp = pyptex('a.tex')` reads in the LaTeX file a.tex and locates all
        Python code fragments contained inside. These Python code fragments are
        executed and their outputs are substituted to produce the `a.pyptex` output file.

        `pyp = pyptex('a.tex', argv)` passes "command-line arguments". The pyptex
        command-line passes `sys.argv[2:]` for this parameter. If omitted, `argv`
        defaults to `[]`. If using PypTeX as an templating engine to generate
        multiple documents from a single source `a.tex` file, one should use
        the `argv` parameter to pass in the various side-parameters needed to generate
        each document. For example, `a.tex` might have the line "Dear @{pyp.argv[0]}""
        One could produce a letter to John by doing `pyp = pyptex('a.tex', ['John'])`.

        `pyp = pyptex('a.tex', argv, latexcommand)` further executes a specific shell
        command once `a.pyptex` has been written to disk (e.g. `pdflatex {pytexfilename}`).
        The default value of `latexcommand` is `False`, in which case no shell command
        is executed.

        Some salient fields of the `pyp=pyptex('a.tex')` class are:

        * `pyp.filename = 'a'` (so `a.tex`, with the extension stripped).
        * `pyp.texfilename = 'a.tex'`.
        * `pyp.cachefilename = 'a.pickle'`.
        * `pyp.bibfilename = 'a.bib'`, used by the `pyp.bib()` function.
        * `pyp.pyptexfilename = 'a.pyptex'`.
        * `pyp.auxfilename = 'a.aux'`, useful in case bibtex is used.
        * `pyp.latex = "pdflatex --file-line-error --synctex=1"`.
          One may overwrite this in a.tex to choose a different latex engine, e.g.
          `pyp.latex = "latex"`.
        * `pyp.latexcommand` defaults to `False`, but the command-line version of `pyptex`
          uses something like.
          `r"{latex} {pyptexfilename} && (test ! -f {bibfilename} || bibtex {auxfilename})"`
          The relevant substitutions are performed by `string.format` from `pyp.__dict__`.
        * `pyp.disable_cache = False`, set this to `True` if you want to disable the `a.pickle`
          cache. You shouldn't need to do this but if your Python code is nondeterministic
          or if tracking dependencies is too hard, disabling all caching will ensure
          that `a.pyptex` is correctly compiled into `a.pdf` and that a stale cache is
          never used.
        * `pyp.deps` is a dictionary of dependencies and timestamps.
        * `pyp.lc` counts lines while parsing.
        * `pyp.argv` stores the ``command-line arguments'' for template generation.
        * `pyp.exitcode` is the exit code of the `pyp.latexcommand`.
        * `pyp.gencount` is the counter for generated files (see `pyp.gen()`).
        * `pyp.fragments` is the list of Python fragments extracted from a.tex.
        * `pyp.outputs` is the matching outputs.
        * `pyp.compiled` is the string that is written to `a.pyptex`.
        * `pyp.autoshow` if True, each figure `fig` is automatically displayed (by `pyp.print`ing
        a suitable `includegraphics` command) at the end of each Python block. When a `fig` is thus
        displayed, `fig.drawn` is set to `True`. Figures that have already been `drawn` are not
        automatically displayed at the end of the Python block.
        """
        print(f'{texfilename}: pyptex compilation begins')
        self.__sympy_plot__ = sympy.plotting.plot(1, show=False).__class__
        self.__globals__ = {'__builtins__': __builtins__, 'pyp': self }
        self.__frozen__ = self.__globals__.copy()
        self.filename = stripext.sub(lambda m: m.group(1),texfilename)
        self.texfilename = texfilename
        matplotlib.use("module://pyptex")
        foo = self.filename+'.tex'
        self.pyptexfilename = foo if foo!=texfilename else f'{self.filename}.pyptex'
        self.cachefilename = f'{self.filename}.pickle'
        self.bibfilename = f'{self.filename}.bib'
        self.auxfilename = f'{self.filename}.aux'
        self.includegraphics = r'\includegraphics[width=\textwidth]{%s}'
        self.latex = 'pdflatex --file-line-error --synctex=1'
        self.latexcommand = latexcommand
        self.disable_cache = False
        self.autoshow = True
        self.__show__ = matplotlib.pyplot.show
        self.deps = {}
        self.bibs = []
        self.lc = 0
        self.argv = [] if argv is None else argv
        self.exitcode = 0
        self.generateddir()
        self.dep(__file__)
        self.compile()
        print(f'{texfilename}: pyptex compilation ends')
    def pp(self, Z, levels: int = 1):
        r"""Pretty-prints the template text string `Z`, using substitutions from the local
        scope that is `levels` calls up on the stack. The template character is @.

        For example, assume the caller has the value `x=3` in its local variables. Then,
        `pp("$x=@x$")` produces `$x=3$`.
        """
        global ppparser
        foo = inspect.currentframe()
        while levels > 0:
            foo = foo.f_back
            levels -= 1
        def do_work(m):
            for k in [1,2]:
                if m.start(k) >= 0:
                    return self.mylatex(eval(m.group(k), foo.f_globals, foo.f_locals))
            raise Exception("Tragic regular expression committed seppuku")

        return ppparser.sub(do_work, Z)

    def run(self, S, k):
        """An internal function for executing Python code."""
        print(f'Executing Python code:\n{S}')
        S = '\n'*k + S
        glob_ = self.__globals__
        doeval = False
        self.__accum__ = []
        with suppress(Exception):
            C = compile(S, self.texfilename, mode='eval')
            doeval = True
        if doeval:
            ret = eval(C, glob_)
            self.__accum__.append(ret)
            if(self.autoshow):
                self.showall()
        else:
            C = compile(S, self.texfilename, mode='exec')
            exec(C, glob_)
            if(self.autoshow):
                self.showall()
        print(f'Python result:\n{self.__accum__!s}')
        return self.__accum__

    def print(self, *argv):
        """If `pyp` is an object of type `pyptex`, `pyp.print(X)` causes `X` to be converted
        to its latex representation and substituted into the `a.pyptex` output file.
        The conversion is given by `sympy.latex(X)`, except that `None` is converted
        to the empty string.

        Many values can be printed at once with the notation `pyp.print(X, Y, ...)`."""
        self.__accum__.extend(argv)

    def cite(self,b):
        r"""If `pyp` is an object of type `pyptex`, then `pyp.cite(X)` adds the relevant
        entry to the bibTeX file and returns the entry name. Example usage:

        `\cite{@{{{pyp.cite(r"@article{seb97,title=Some title etc...}")}}}}`
        """
        self.bibs.append(b)
        return bibentryname.match(b).group(1).strip()

    def process(self, S, runner):
        """An internal helper function for parsing the input file."""
        ln = numpy.cumsum(numpy.array(numpy.array(list(S), dtype='U1') == '\n', int))
        ln = numpy.insert(ln, 0, 0)

        def do_work(m):
            if m.start(1) >= 0:
                return m.group(0)
            if m.start(2) >= 0:
                return '@'
            for k in [6,9]:
                if m.start(k) >= 0:
                    z = m.group(k)
                    z0 = m.start(k)
                    z1 = m.end(k)
                    o = m.group(k-1) or ''
                    break
            self.lc += ln[z1] - ln[z0] + 1
            return runner(z, ln[z0], o)

        return pypparser.sub(do_work, S)

    __pdoc__['mylatex'] = False
    def mylatex(self, X):
        if X is None:
            return ''
        if isinstance(X, str):
            return X
        if isinstance(X,pyptexNameSpace):
            return str(X)
        if isinstance(X,matplotlib.pyplot.Figure):
            self.__setupfig__(X)
            X.drawn = True
            return X.__IG__
        if isinstance(X,self.__sympy_plot__):
            return ""
        return sympy.latex(X)

    def compile(self):
        """An internal function for compiling the input file."""
        with open(self.texfilename, 'rt') as file:
            text = file.read()
        try:
            with open(self.cachefilename, 'rb') as file:
                cache = pickle.load(file)
        except Exception:
            cache = {}
        defaults = {
            'fragments': [],
            'outputs': [],
            'deps': {},
            'argv': [],
            'disable_cache': True,
        }
        for k, v in defaults.items():
            if k not in cache:
                cache[k] = v
        self.fragments = []

        def scanner(C, k, o):
            self.fragments.append(C)
            assert o in ['','verbatim'],"Invalid option: "+o
            return ''

        self.process(text, runner=scanner)
        print(f'Found {self.lc!s} lines of Python.')
        saveddeps = self.deps
        self.deps = {}
        for k in cache['deps']:
            self.dep(k)
        self.resolvedeps()
        cached = True
        if cache['disable_cache']:
            print('disable_cache=True')
            cached = False
        elif cache['argv'] != self.argv:
            print('argv differs', self.argv, cache['argv'])
            cached = False
        elif cache['fragments'] != self.fragments:
            F1 = dict(enumerate(cache['fragments']))
            F2 = dict(enumerate(self.fragments))
            k = dictdiff(F1, F2)[0]
            print('Fragment #', k,
                  '\nCached version:\n', F1[k] if k in F1 else None,
                  '\nLive version:\n', F2[k] if k in F2 else None)
            cached = False
        elif self.deps != cache['deps']:
            F1 = cache['deps']
            F2 = self.deps
            k = dictdiff(F1, F2)[0]
            print('Dependency mismatch', k,
                  '\nCached version:\n', F1[k] if k in F1 else None,
                  '\nLive version:\n', F2[k] if k in F2 else None)
            cached = False
        if cached:
            print('Using cached Python outputs')
            for k, v in cache.items():
                self.__dict__[k] = v
            self.subcount = -1

            def subber(C, k, o):
                self.subcount += 1
                if(o==''):
                    return self.outputs[self.subcount]
                if(o=='verbatim'):
                    return C

            self.compiled = self.process(text, runner=subber)
        else:
            print('Cache is invalidated.')
            self.deps = saveddeps
            self.outputs = []

            def appender(C, k, o):
                result = self.run(C, k)
                self.outputs.append(''.join(map(self.mylatex, result)))
                if(o==''):
                    return self.outputs[-1]
                if(o=='verbatim'):
                    return C

            self.compiled = self.process(text, runner=appender)
        sys.stdout.flush()
        if self.pyptexfilename:
            print(f'Saving to file: {self.pyptexfilename}')
            with open(self.pyptexfilename, 'wt') as file:
                file.write(self.compiled)
        self.resolvedeps()
        print(f'Dependencies are:\n{self.deps!s}')
        if not cached:
            print('Saving cache file', self.cachefilename)
            with open(self.cachefilename, 'wb') as file:
                cache = {}
                for k, v in self.__dict__.items():
                    if k[0:2] == '__' and k[-2:] == '__':
                        pass
                    elif callable(v):
                        pass
                    else:
                        cache[k] = v
                pickle.dump(cache, file)
        if self.latexcommand:
            cmd = self.latexcommand.format(**self.__dict__)
            print(f'Running Latex command:\n{cmd}')
            self.exitcode = os.system(cmd)

    def bib(self, bib=""):
        """A helper function for creating a `.bib` file. If `pyp=pyptex('a.tex')`,
        then `pyp.bib('''@book{knuth1984texbook, title={The {TEXbook}},
        author={Knuth, Donald Ervin and Bibby, Duane}}''')` creates a file
        `a.bib` with the given text. This is just a convenience function
        that makes it easier to incorporate the bibtex file straight into the
        `a.tex` source. In `a.tex`, the typical way of using it is:
        `\\bibliography{@{{{pyp.bib("...")}}}}`.
        """
        self.bibs.append(bib)
        with self.open(self.bibfilename, 'wt') as file:
            file.write("\n".join(self.bibs))
        return self.filename

    def dep(self, filename):
        """If `pyp=pyptex('a.tex')`, then `pyp.dep(filename)` declares that the Python code
        in `a.tex` depends on the file designated by `filename`. When the object
        `pyptex('a.tex')` is constructed, the file `a.pickle` will be loaded (if it exists).
        `a.pickle` is a cache of the results of the Python calculations in `a.tex`.
        If the cache is deemed valid, the `pyptex` constructor does not rerun all
        the Python fragments in `a.tex` but instead uses the previously cached outputs.

        The cache is invalidated under the following scenarios:
        1. The new Python fragments in `a.tex` are not identical to the cached fragments.
        2. The "last modification" timestamp on dependencies is not the same as in the cache.
        3. `pyp.disable_cache==True`.

        The list of dependencies defaults to only the `pyptex` executable. Additional
        dependencies can be manually declared via `pyp.dep(filename)`.

        For convenience, `pyp.dep(filename)` returns filename.
        """
        self.deps[filename] = ''
        return filename

    def resolvedeps(self):
        """An internal function that actually computes the datestamps of dependencies."""
        for k in self.deps:
            try:
                ds = format_my_nanos(os.stat(k).st_mtime_ns)
            except Exception:
                ds = ''
            self.deps[k] = ds

    def input(self, filename, argv=False):
        r"""If `pyp = pyptex('a.tex')` then
        `pyp.input('b.tex')`
        returns the string `\input{"b.pyptex"}`. The common way of using this is to
        put `@{pyp.input('b.tex')}` somewhere in `a.tex`.
        The function `pyp.input('b.tex')` internally calls the constructor
        `pyptex('b.tex')` so that `b.pyptex` is compiled from `b.tex`.

        Note that the two files `a.tex` and `b.tex` are "semantically isolated". All
        calculations, variables and functions defined in `a.tex` live in a global scope
        that is private to `a.tex`, much like each Python module has a private global
        scope. In a similar fashion, `b.tex` has its own private global scope.
        The global `pyp` objects in `a.tex` and `b.tex` are also different instances
        of the `pyptex` class. This is similar to the notion of "compilation units" in
        the C programming language.

        From `a.tex`, one can retrieve global variables of `b.tex` as follows. If
        `foo = pyp.input('b.tex')`, and if `b.tex` defines a global variable `x`,
        then it can be retrieved by `foo.x`. The `foo` variable is an instance of a
        `pyptexNameSpace` that contains the global scope of `b.tex`. This type has a
        custom string representation, so that `str(foo)` or `@{foo}` is
        `'\input{b.pyptex}'`.

        If one wishes to pass some parameters from `a.tex` to `b.tex`, one may use
        the notation `pyp.input('b.tex', argv)`, which will initialize the global
        `pyp` object of `b.tex` so that it contains the field `pyp.argv=argv`.
        """
        ret = pyptex(filename, argv or self.argv, False)
        ret2 = pyptexNameSpace(ret.__globals__)
        return ret2

    def open(self, filename, *argv, **kwargs):
        """If pyp = pyptex('a.tex') then pyp.open(filename, ...) is a wrapper for
        the builtin function open(filename, ...) that further adds filename to
        the list of dependencies via pyp.dep(filename).
        """
        self.dep(filename)
        return open(filename, *argv, **kwargs)


def pyptexmain(argv: list = None):
    """This function parses an input file a.tex to produce a.pyptex and a.pdf, by
    doing pyp = pyptex('a.tex', ...) object. The filename a.tex must be in argv[1];
    if argv is not provided, it is taken from sys.argv.
    The default pyp.latexcommand invokes pdflatex and, if a.bib is present, also bibtex.
    If an exception occurs, pdb is automatically invoked in postmortem mode.
    If "--pdb=no" is in argv, it is removed from argv and automatic pdb postmortem is disabled.
    If "--pdb=yes" is in argv, automatic pdb postmortem is enabled. This is the default.
    """
    argv = argv or sys.argv
    dopdb = True
    with suppress(Exception):
        argv.remove('--pdb=no')
        dopdb = False
    with suppress(Exception):
        argv.remove('--pdb=yes')
        dopdb = True
    if len(argv) < 2:
        print('Usage: pyptex <filename.tex> ...')
        sys.exit(1)
    writer = streamcapture.Writer(open(f'{os.path.splitext(argv[1])[0]}.pyplog','wb'),2)
    with streamcapture.StreamCapture(sys.stdout,writer), streamcapture.StreamCapture(sys.stderr,writer):
        try:
            pyp = pyptex(argv[1], argv[2:],
                latexcommand=r'{latex} {pyptexfilename} && (test ! -f {bibfilename} || bibtex {auxfilename})')
        except Exception:
            import pdb
            traceback.print_exc(file=sys.stdout)
            if dopdb:
                print('A Python error has occurred. Launching the debugger pdb.\n'
                      "Type 'help' for a list of commands, and 'quit' when done.")
                pdb.post_mortem()
            sys.exit(1)
    return pyp.exitcode
