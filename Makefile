PYTHON = python
SWIG_FLAGS = -c++ -python -naturalvar -builtin -O

CXX_SRC := $(shell find include/tom -type f -name '*.h' -o -name '*.cpp' -o -name '*.hpp')
SWIG_SRC := $(shell find swig -type f -name "*.i")
PY_SRC := $(shell find python/tom -type f -name "*.py")

.PHONY: build
.PHONY: install install_user
.PHONY: test debug
.PHONY: doc swig clean cleanall
.PHONY: deploy deploy_quickly deploy_optimized
.PHONY: tom

build: swig/_tomlib_wrap.cpp
	$(PYTHON) setup.py build_ext

install: swig/_tomlib_wrap.cpp
	$(PYTHON) setup.py install

install_user: swig/_tomlib_wrap.cpp
	$(PYTHON) setup.py install --user

test: swig/_tomlib_wrap.cpp
	CPPFLAGS="-DTOM_DEBUG -g" $(PYTHON) setup.py test

debug: swig/_tomlib_wrap.cpp
	CPPFLAGS="-DTOM_DEBUG -g" $(PYTHON) setup.py build_ext

deploy: swig/_tomlib_wrap.cpp
	CC=clang++ CXX=clang++ CPPFLAGS="-gline-tables-only -march=native -O2 -DEIGEN_USE_BLAS -framework Accelerate" $(PYTHON) setup.py install --user

deploy_optimized: swig/_tomlib_wrap.cpp
	CC=g++-mp-6 CXX=g++-mp-6 CPPFLAGS="-Wa,-q -g0 -march=native -O2 -DEIGEN_USE_BLAS -framework Accelerate" $(PYTHON) setup.py install --user

doc:
	doxygen doc/tom.doxyfile

tom: $(CXX_SRC)
	g++ -std=c++11 -I/opt/local/include/eigen3 -Iinclude/tom -Iinclude/external src/tom.cpp -o tom

swig: swig/tomdoc.i
	swig $(SWIG_FLAGS) -Iswig -outdir python/tom -o swig/_tomlib_wrap.cpp swig/_tomlib.i

clean:
	@rm -f python/tom/__tomlib.so
	@$(PYTHON) setup.py -q clean --all 2>/dev/null
	@find . | grep -E "(__pycache__|\.pyc|\.egg-info)$$" | xargs rm -rf
	@rm -rf dist build

cleanall: clean
	@rm -rf doc/html doc/xml doc/latex
	@rm -f swig/tomdoc.i
	@rm -f swig/_tomlib_wrap.cpp swig/_tomlib_wrap.h python/tom/_tomlib.py

doc/xml/index.xml: $(CXX_SRC) doc/tom_xml.doxyfile
	doxygen doc/tom_xml.doxyfile

swig/tomdoc.i: doc/doxy2swig.py doc/xml/index.xml
	$(PYTHON) doc/doxy2swig.py -focaq doc/xml/index.xml swig/tomdoc.i

swig/_tomlib_wrap.cpp: Makefile $(CXX_SRC) $(SWIG_SRC) swig/tomdoc.i
	swig $(SWIG_FLAGS) -Iswig -outdir python/tom -o swig/_tomlib_wrap.cpp swig/_tomlib.i
