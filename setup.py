#!/usr/bin/env python3

import subprocess, sys, os, argparse,shutil
from collections import namedtuple, defaultdict
sys.path.append(os.path.join(os.path.dirname(__file__), "scripts/pyUtils"))
sys.path.append(os.path.join(os.path.dirname(__file__), "scripts/setUpScripts"))
from utils import Utils
from genFuncs import genHelper
from color_text import ColorText as CT
import pickle, datetime, re, math

#tuples
BuildPaths = namedtuple("BuildPaths", 'url build_dir build_sub_dir local_dir')
LibNameVer = namedtuple("LibNameVer", 'name version')
LibNameVerCommit = namedtuple("LibNameVerCommit", 'name version commit')
GitRefs = namedtuple("GitRefs", "branches tags")


class LibDirMaster():
    def __init__(self,externalLoc):
        self.base_dir = os.path.abspath(externalLoc); #top dir to hold tars,build, local directories

        self.ext_tars = os.path.join(self.base_dir, "tarballs") #location to keep tarballs of programs/libraries downloads
        self.ext_build = os.path.join(self.base_dir, "build") #location for the building of programs/libraries
        self.install_dir = os.path.join(self.base_dir, "local") #location for the final install of programs/libraries
        self.cache_dir = os.path.join(self.base_dir, ".cache")

        Utils.mkdir(self.ext_tars) #tar storage directory
        Utils.mkdir(self.ext_build) #build directory
        Utils.mkdir(self.install_dir) #local directory
        Utils.mkdir(self.cache_dir) #cache directory

def joinNameVer(libNameVerTup):
    return os.path.join(libNameVerTup.name, libNameVerTup.version, libNameVerTup.name)

class CPPLibPackageVersionR():
    def __init__(self, name, url, version, dirMaster):
        self.nameVer_ = LibNameVer(name, version)
        build_dir = os.path.join(dirMaster.ext_build, name, version)
        fn = os.path.basename(url)
        fn_noex = fn.replace(".tar.gz", "").replace(".tar.bz2", "").replace(".git", "")
        build_sub_dir = os.path.join(dirMaster.ext_build, name, version, fn_noex)
        local_dir = os.path.join(dirMaster.install_dir, name, version, name)
        self.bPaths_ = BuildPaths(url, build_dir, build_sub_dir, local_dir)
        self.rInstallLoc_ = ""
        self.rExecutable_ = ""
        self.rHome_ = ""
        self.depends_ = []
        self.cmd_ = ""


    def setExecutableLoc(self, localPath):
        self.rInstallLoc_ = os.path.join(os.path.abspath(localPath), joinNameVer(self.nameVer_))
        verSplit = self.nameVer_.version.split(".")
        verNameStr = verSplit[0] + verSplit[1] + verSplit[2]
        verNameInt = int(verNameStr)
        #print verSplit
        #print verNameStr
        #print verNameInt
        #sys.exit(1)

        if Utils.isMac() and verNameInt < 330:
            self.rExecutable_ = os.path.join(self.rInstallLoc_, "R.framework/Resources/bin/R")
        else:
            self.rExecutable_ = os.path.join(self.rInstallLoc_, "bin/R")
        self.rHome_ = str(Utils.runAndCapture(self.rExecutable_ + " RHOME")).strip()

    def getIncludeFlags(self, localPath):
        self.setExecutableLoc(localPath)
        ret = "-DSTRICT_R_HEADERS"
        ret = ret + " " + Utils.runAndCapture(self.rExecutable_ + " CMD config --cppflags")
        ret = ret + " " + Utils.runAndCapture("echo '.libPaths(.libPaths()[length(.libPaths()  )] ); Rcpp:::CxxFlags()' | " + self.rExecutable_ + " --vanilla --slave")
        ret = ret + " " + Utils.runAndCapture("echo '.libPaths(.libPaths()[length(.libPaths()  )] ); RInside:::CxxFlags()' | " + self.rExecutable_ + " --vanilla --slave")
        return ' '.join(ret.split())

    def getLdFlags(self, localPath):
        self.setExecutableLoc(localPath)
        ret = ""
        ret = ret + Utils.runAndCapture(self.rExecutable_ + " CMD config --ldflags")
        ret = ret + " " + Utils.runAndCapture(self.rExecutable_ + " CMD config BLAS_LIBS")
        ret = ret + " " + Utils.runAndCapture(self.rExecutable_ + " CMD config LAPACK_LIBS")
        ret = ret + " " + "-Wl,-rpath," + self.rHome_ + "/lib"
        ret = ret + " " + Utils.runAndCapture("echo '.libPaths(.libPaths()[length(.libPaths()  )] ); Rcpp:::LdFlags()' | " + self.rExecutable_ + " --vanilla --slave")
        ret = ret + " " + Utils.runAndCapture("echo '.libPaths(.libPaths()[length(.libPaths()  )] ); RInside:::LdFlags()' | " + self.rExecutable_ + " --vanilla --slave")
        return ' '.join(ret.split())

    def getDownloadUrl(self):
        return self.bPaths_.url



class CPPLibPackageVersion():
    def __init__(self, name, version, bPaths, depends, commit = ""):
        self.nameVer_ = LibNameVer(name, version)
        if "" !=commit:
            self.nameVer_ = LibNameVerCommit(name, version, commit)
        self.depends_ = depends #should be a list of LibNameVer or LibNameVerCommit
        self.bPaths_ = bPaths
        self.includePath_ = os.path.join(joinNameVer(self.nameVer_), "include")
        self.additionalIncludeFlags_ = []
        self.additionalIncludePaths_ = []
        self.libPath_ = os.path.join(joinNameVer(self.nameVer_), "lib")
        self.additionalLdFlags_ = []
        self.libName_ = name
        self.altLibName_ = ""
        self.cmd_ = ""


    def getDownloadUrl(self):
        ret = self.bPaths_.url
        if str(self.bPaths_.url).endswith(".git"):
            ret = self.bPaths_.url.replace(".git","/archive/" + str(self.nameVer_.version) + ".tar.gz").replace("git@github.com:", "https://github.com/")
        return ret

    def getIncludeFlags(self, localPath):
        ret = ""
        if(len(self.includePath_) > 0):
            #ret = "-isystem" + str(os.path.join(localPath, self.includePath_))
            ret = "-I" + str(os.path.join(localPath, self.includePath_))
        if len(self.additionalIncludePaths_) > 0:
            for addPath in self.additionalIncludePaths_:
                if len(ret) > 0:
                    ret = ret + " "
                #ret = ret + "-isystem" + str(os.path.join(localPath, addPath))
                ret = ret + "-I" + str(os.path.join(localPath, addPath))
        if len(self.additionalIncludeFlags_) > 0:
            if len(ret)> 0:
                ret = ret + " "
            ret = ret + " ".join(self.additionalIncludeFlags_)
        return ret

    def getLdFlags(self, localPath):
        ret = ""
        retList = []
        libPath = str(os.path.join(localPath,self.libPath_))
        if(len(self.libPath_) > 0):
            retList.append("-Wl,-rpath," + str(libPath))
            retList.append("-L" + str(libPath))
            if len(self.altLibName_) > 0:
                retList.append("-l" + self.altLibName_)
            elif "" != self.libName_:
                retList.append("-l" + self.libName_)
        if len(self.additionalLdFlags_) > 0:
            retList.extend(self.additionalLdFlags_)
        if len(retList) > 0:
            ret = " ".join(retList)
        return ret


class CPPLibPackage():
    def __init__(self, name, defaultBuildCmd, dirMaster, libType, defaultVersion):
        self.name_ = name

        self.defaultVersion_ = defaultVersion.replace("/", "__")
        self.defaultBuildCmd_ = defaultBuildCmd
        self.versions_ = {}
        self.externalLibDir_ = dirMaster
        if "git" != libType and "file" != libType and "git-headeronly" != libType:
            raise Exception("libType should be 'git', 'git-headeronly', or 'file', not " + str(libType))
        self.libType_ = libType #should be git, git-headeronly, or file
        self.njhProject_ = False

    def addVersion(self, url, verName, depends=[]):
        verName = verName.replace("/", "__")
        #fn = os.path.basename(url)
        #fn_noex = fn.replace(".tar.gz", "").replace(".tar.bz2", "").replace(".git", "")
        build_dir = os.path.join(self.externalLibDir_.ext_build, self.name_, verName)
        build_sub_dir = os.path.join(self.externalLibDir_.ext_build, self.name_, verName, self.name_)
        local_dir = os.path.join(self.externalLibDir_.install_dir, self.name_, verName, self.name_)
        self.versions_[verName] = CPPLibPackageVersion(self.name_, verName, BuildPaths(url, build_dir, build_sub_dir, local_dir), depends)

    def addHeaderOnlyVersion(self, url, verName, depends=[]):
        '''set up for header only libraries, these just need
         the header copied no need for build_dir build_sub_dir '''
        verName = verName.replace("/", "__")
        local_dir = os.path.join(self.externalLibDir_.install_dir, self.name_, verName, self.name_)
        self.versions_[verName] = CPPLibPackageVersion(self.name_, verName,BuildPaths(url, "", "", local_dir), depends)
        self.versions_[verName].includePath_ = os.path.join(self.name_, verName)
        #self.versions_[verName].includePath_ = joinNameVer(self.versions_[verName].nameVer_)
        self.versions_[verName].libPath_ = ""

    def hasVersion(self, version):
        return version in self.versions_

    def getVersions(self):
        return sorted(self.versions_.keys())

    def getLocalDir(self, version):
        if self.hasVersion(version):
            return self.versions_[version].bPaths_.local_dir
        raise Exception("Error in getLocalDir" + self.name_ + " doesn't have version " + str(version))

    def getBuildSubDir(self, version):
        if self.hasVersion(version):
            return self.versions_[version].bPaths_.build_sub_dir
        raise Exception("Error in getBuildSubDir" + self.name_ + " doesn't have version " + str(version))

    def getBuildDir(self, version):
        if self.hasVersion(version):
            return self.versions_[version].bPaths_.build_dir
        raise Exception("Error in getBuildDir" + self.name_ + " doesn't have version " + str(version))

    def getGitRefs(self, url):
        if not self.libType_.startswith("git"):
            raise Exception("Library " + self.name_ + " is not a git library, type is : " + self.libType_)
        try:
            cap = Utils.runAndCapture("git ls-remote {url}".format(url = url))
        except Exception as inst:
            try:
                #if the first attempt fail, try doing https instead if that was reason
                url = url.replace("git@github.com:", "https://github.com/")
                cap = Utils.runAndCapture("git ls-remote {url}".format(url = url))
            except Exception as instFallback:
                raise instFallback
        branches = []
        tags = []
        for line in cap.split("\n"):
            if "" != line:
                lineSplit = line.split()
                if 2 == len(lineSplit):
                    if "heads" in lineSplit[1]:
                        branches.append(lineSplit[1][(lineSplit[1].find("heads/") + 6):])
                    elif "tags" in lineSplit[1] and not lineSplit[1].endswith("^{}"):
                        tags.append(lineSplit[1][(lineSplit[1].find("tags/") + 5):])
        gRefs = GitRefs(branches, tags)
        return (gRefs)


class Packages():
    '''class to hold and setup all the necessary paths for
    downloading, building, and then installing packages/libraries'''
    def __init__(self, externalLoc, args, libsNeeded = []):
        self.dirMaster_ = LibDirMaster(externalLoc); #top dir to hold tars, build, local directories
        self.args = args
        self.packages_ = {} #dictionary to hold path infos
        self.setUpPackagesNeeded(libsNeeded);

    def setUpPackagesNeeded(self, libsNeeded):
        if "boost" in libsNeeded:
            self.packages_["boost"] = self.__boost()
        if "r" in libsNeeded:
            self.packages_["r"] = self.__r()
        if "cppcms" in libsNeeded:
            self.packages_["cppcms"] = self.__cppcms()
        if "dlib" in libsNeeded:
            self.packages_["dlib"] = self.__dlib()
        if "libsvm" in libsNeeded:
            self.packages_["libsvm"] = self.__libsvm()
        if "mathgl" in libsNeeded:
            self.packages_["mathgl"] = self.__mathgl()
        if "magic" in libsNeeded:
            self.packages_["magic"] = self.__magic()
        if "bowtie2" in libsNeeded:
            self.packages_["bowtie2"] = self.__bowtie2()
        if "pigz" in libsNeeded:
            self.packages_["pigz"] = self.__pigz()
        if "lastz" in libsNeeded:
            self.packages_["lastz"] = self.__lastz()
        if "samtools" in libsNeeded:
            self.packages_["samtools"] = self.__samtools()
        if "bcftools" in libsNeeded:
            self.packages_["bcftools"] = self.__bcftools()
        if "eigen" in libsNeeded:
            self.packages_["eigen"] = self.__eigen()
        if "glpk" in libsNeeded:
            self.packages_["glpk"] = self.__glpk()
        if "lapack" in libsNeeded:
            self.packages_["lapack"] = self.__lapack()
        if "atlas" in libsNeeded:
            self.packages_["atlas"] = self.__atlas()

        #git repos
        if "adapterremoval" in libsNeeded:
            self.packages_["adapterremoval"] = self.__adapterremoval()
        if "curl" in libsNeeded:
            self.packages_["curl"] = self.__curl()
        if "mongoc" in libsNeeded:
            self.packages_["mongoc"] = self.__mongoc()
        if "mongocxx" in libsNeeded:
            self.packages_["mongocxx"] = self.__mongocxx()
        if "flash" in libsNeeded:
            self.packages_["flash"] = self.__flash()
        if "libpca" in libsNeeded:
            self.packages_["libpca"] = self.__libpca()
        if "muscle" in libsNeeded:
            self.packages_["muscle"] = self.__muscle()
        if "armadillo" in libsNeeded:
            self.packages_["armadillo"] = self.__armadillo()
        if "cmake" in libsNeeded:
            self.packages_["cmake"] = self.__cmake()
        if "boost_filesystem" in libsNeeded:
            self.packages_["boost_filesystem"] = self.__boost_filesystem()
        if "boost_math" in libsNeeded:
            self.packages_["boost_math"] = self.__boost_math()
        if "zlib" in libsNeeded:
            self.packages_["zlib"] = self.__zlib()
        if "bamtools" in libsNeeded:
            self.packages_["bamtools"] = self.__bamtools()
        if "jsoncpp" in libsNeeded:
            self.packages_["jsoncpp"] = self.__jsoncpp()
        if "catch" in libsNeeded:
            self.packages_["catch"] = self.__catch()
        if "hts" in libsNeeded:
            self.packages_["hts"] = self.__hts()
        if "zi_lib" in libsNeeded:
            self.packages_["zi_lib"] = self.__zi_lib()
        if "pstreams" in libsNeeded:
            self.packages_["pstreams"] = self.__pstreams()
        if "cppitertools" in libsNeeded:
            self.packages_["cppitertools"] = self.__cppitertools()
        if "cppprogutils" in libsNeeded:
            self.packages_["cppprogutils"] = self.__cppprogutils()
        if "restbed" in libsNeeded:
            self.packages_["restbed"] = self.__restbed()
        if "zlib-ng" in libsNeeded:
            self.packages_["zlib-ng"] = self.__zlibng()
        if "openblas" in libsNeeded:
            self.packages_["openblas"] = self.__openblas()
        if "unqlite" in libsNeeded:
            self.packages_["unqlite"] = self.__unqlite()


        #njh setup
        if "njhseq" in libsNeeded:
            self.packages_["njhseq"] = self.__njhseq()
        if "njhcpp" in libsNeeded:
            self.packages_["njhcpp"] = self.__njhcpp()
        if "seekdeep" in libsNeeded:
            self.packages_["seekdeep"] = self.__SeekDeep()
        if "seqserver" in libsNeeded:
            self.packages_["seqserver"] = self.__seqserver()
        if "njhrinside" in libsNeeded:
            self.packages_["njhrinside"] = self.__njhRInside()
        if "twobit" in libsNeeded:
            self.packages_["twobit"] = self.__twobit()
        if "sharedmutex" in libsNeeded:
            self.packages_["sharedmutex"] = self.__sharedMutex()
        if "bhtsne" in libsNeeded:
            self.packages_["bhtsne"] = self.__bhtsne()
        if "elucidator" in libsNeeded:
            self.packages_["elucidator"] = self.__elucidator()
        if "pathweaver" in libsNeeded:
            self.packages_["pathweaver"] = self.__pathweaver()
        if "mipwrangler" in libsNeeded:
            self.packages_["mipwrangler"] = self.__MIPWrangler()
        #developer, private repos
        if self.args.private:
            if "elucidatorlab" in libsNeeded:
                self.packages_["elucidatorlab"] = self.__elucidatorlab()
        '''

        self.packages_["mlpack"] = self.__mlpack()
        self.packages_["liblinear"] = self.__liblinear()
        '''

    def package(self, name):
        '''get package info if it exists'''
        if name in self.packages_:
            return self.packages_[name]
        raise Exception(name + " not found in Packages")

    def __zi_lib(self):
        name = "zi_lib"
        url = 'https://github.com/weng-lab/zi_lib.git'
        buildCmd = ""
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git-headeronly", "master")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addHeaderOnlyVersion(url, ref)
                pack.versions_[ref].includePath_ = os.path.join(name, ref, name)
                if not Utils.isMac():
                    pack.versions_[ref].additionalLdFlags_ = ["-lrt"]
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __pstreams(self):
        name = "pstreams"
        url = 'https://github.com/nickjhathaway/pstreams.git'
        buildCmd = ""
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git-headeronly", "RELEASE_0_8_1")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addHeaderOnlyVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack



    def __bamtools(self):
        url = 'https://github.com/nickjhathaway/bamtools.git'
        name = "bamtools"
        buildCmd = "mkdir -p build && cd build && ZLIBADDFLAGS CC={CC} CXX={CXX} cmake -DCMAKE_INSTALL_PREFIX:PATH={local_dir} .. && make -j {num_cores} install"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v2.5.0")
        defaultZlibVersion = "1.3.1";
        zlibPack = self.__zlib()
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref, [LibNameVer("zlib", defaultZlibVersion)])
                zlibLdFlags = zlibPack.versions_[defaultZlibVersion].getLdFlags(self.dirMaster_.install_dir)
                zlibIncFlags = zlibPack.versions_[defaultZlibVersion].getIncludeFlags(self.dirMaster_.install_dir)
                zlibAddFlags = "LDFLAGS=\""+ zlibLdFlags + "\" CXXFLAGS=\""+ zlibIncFlags + "\""
                pack.versions_[ref].cmd_ = buildCmd.replace("ZLIBADDFLAGS", zlibAddFlags)
                pack.versions_[ref].libPath_ = os.path.join(pack.versions_[ref].libPath_,name)
                pack.versions_[ref].includePath_ = os.path.join(pack.versions_[ref].includePath_,name)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __jsoncpp(self):
        url = "https://github.com/open-source-parsers/jsoncpp.git"
        name = "jsoncpp"
        buildCmd = "mkdir -p build && cd build && CC={CC} CXX={CXX} cmake -DCMAKE_CXX_FLAGS=-fPIC -DCMAKE_EXE_LINKER_FLAGS=-fPIC -DCMAKE_INSTALL_PREFIX:PATH={local_dir} ..  && make -j {num_cores} install"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "1.8.3")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __mongoc(self):
        url = "https://github.com/mongodb/mongo-c-driver.git"
        name = "mongoc"
#
#        if Utils.isMac():
#            buildCmd = "sed -i.bak s/git:/http:/g .gitmodules && CC={CC} CXX={CXX}  PKG_CONFIG_PATH=/usr/local/opt/openssl/lib/pkgconfig:$PKG_CONFIG_PATH ./autogen.sh --enable-ssl --enable-sasl --prefix={local_dir}&& make -j {num_cores}  && make install"
#        else:
#            buildCmd = "sed -i.bak s/git:/http:/g .gitmodules && CC={CC} CXX={CXX} ./autogen.sh --enable-ssl --enable-sasl --prefix={local_dir} && make -j {num_cores}  && make install"
#
        if Utils.isMac():
            buildCmd = r"""sed -i.bak s/git:/http:/g .gitmodules && CC={CC} CXX={CXX} PKG_CONFIG_PATH=/usr/local/opt/openssl/lib/pkgconfig:$PKG_CONFIG_PATH LDFLAGS="$(echo $(pkg-config openssl --libs) | sed 's/-L/-Wl,-rpath,/g' | sed 's/lib\ .*/lib/g')" ./autogen.sh --enable-ssl --enable-sasl --prefix={local_dir}&& make -j {num_cores}  && make install"""
        else:
            buildCmd = r"""sed -i.bak s/git:/http:/g .gitmodules && CC={CC} CXX={CXX} LDFLAGS="$(echo $(pkg-config openssl --libs) | sed 's/-L/-Wl,-rpath,/g' | sed 's/lib\ .*/lib/g')" ./autogen.sh --enable-ssl --enable-sasl --prefix={local_dir} && make -j {num_cores}  && make install"""
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "1.3.3")
        pack.addVersion(url, "1.3.3")
        pack.versions_["1.3.3"].additionalIncludePaths_.append(pack.versions_["1.3.3"].includePath_ + "/libmongoc-1.0")
        pack.versions_["1.3.3"].includePath_ = pack.versions_["1.3.3"].includePath_ + "/libbson-1.0"
        pack.versions_["1.3.3"].altLibName_ = "ssl" #a trick to control order of -l flags for libs
        pack.versions_["1.3.3"].additionalLdFlags_ = ["-lcrypto","-lmongoc-1.0", "-lbson-1.0"]
        if not Utils.isMac():
            pack.versions_["1.3.3"].additionalLdFlags_.append("-lrt")
        pack.addVersion(url, "1.3.4")
        pack.versions_["1.3.4"].additionalIncludePaths_.append(pack.versions_["1.3.4"].includePath_ + "/libmongoc-1.0")
        pack.versions_["1.3.4"].includePath_ = pack.versions_["1.3.4"].includePath_ + "/libbson-1.0"
        pack.versions_["1.3.4"].altLibName_ = "ssl" #a trick to control order of -l flags for libs
        pack.versions_["1.3.4"].additionalLdFlags_ = ["-lcrypto","-lmongoc-1.0", "-lbson-1.0"]
        if not Utils.isMac():
            pack.versions_["1.3.4"].additionalLdFlags_.append("-lrt")
        pack.addVersion(url, "1.4.1")
        pack.versions_["1.4.1"].additionalIncludePaths_.append(pack.versions_["1.4.1"].includePath_ + "/libmongoc-1.0")
        pack.versions_["1.4.1"].includePath_ = pack.versions_["1.4.1"].includePath_ + "/libbson-1.0"
        pack.versions_["1.4.1"].altLibName_ = "ssl" #a trick to control order of -l flags for libs
        pack.versions_["1.4.1"].additionalLdFlags_ = ["-lcrypto","-lmongoc-1.0", "-lbson-1.0"]
        if not Utils.isMac():
            pack.versions_["1.4.1"].additionalLdFlags_.append("-lrt")
        pack.addVersion(url, "1.5.0")
        pack.versions_["1.5.0"].additionalIncludePaths_.append(pack.versions_["1.5.0"].includePath_ + "/libmongoc-1.0")
        pack.versions_["1.5.0"].includePath_ = pack.versions_["1.5.0"].includePath_ + "/libbson-1.0"
        pack.versions_["1.5.0"].altLibName_ = "ssl" #a trick to control order of -l flags for libs
        pack.versions_["1.5.0"].additionalLdFlags_ = ["-lcrypto","-lmongoc-1.0", "-lbson-1.0"]
        if not Utils.isMac():
            pack.versions_["1.5.0"].additionalLdFlags_.append("-lrt")
        return pack#

    def __mongocxx(self):
        url = "https://github.com/mongodb/mongo-cxx-driver.git"
        name = "mongocxx"
        buildCmd = "cd build && PKG_CONFIG_PATH={external}/local/mongoc/{mongoc_ver}/mongoc/lib/pkgconfig/:PKG_CONFIG_PATH CC={CC} CXX={CXX} cmake -DCMAKE_BUILD_TYPE=Release -DLIBBSON_DIR={external}/local/mongoc/{mongoc_ver}/mongoc/ -DLIBMONGOC_DIR={external}/local/mongoc/{mongoc_ver}/mongoc/ -DCMAKE_INSTALL_PREFIX={local_dir} .. && make -j {num_cores} && make install"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "r3.0.1")
        pack.addVersion(url, "r3.0.0", [LibNameVer("mongoc", "1.3.3")])
        pack.versions_["r3.0.0"].additionalIncludePaths_.append(pack.versions_["r3.0.0"].includePath_ + "/mongocxx/v_noabi")
        pack.versions_["r3.0.0"].includePath_ = pack.versions_["r3.0.0"].includePath_ + "/bsoncxx/v_noabi"
        pack.versions_["r3.0.0"].additionalLdFlags_ = ["-lbsoncxx"]
        pack.addVersion(url, "r3.0.1", [LibNameVer("mongoc", "1.3.4")])
        pack.versions_["r3.0.1"].additionalIncludePaths_.append(pack.versions_["r3.0.1"].includePath_ + "/mongocxx/v_noabi")
        pack.versions_["r3.0.1"].includePath_ = pack.versions_["r3.0.1"].includePath_ + "/bsoncxx/v_noabi"
        pack.versions_["r3.0.1"].additionalLdFlags_ = ["-lbsoncxx"]
        pack.addVersion(url, "r3.0.2", [LibNameVer("mongoc", "1.4.1")])
        pack.versions_["r3.0.2"].additionalIncludePaths_.append(pack.versions_["r3.0.2"].includePath_ + "/mongocxx/v_noabi")
        pack.versions_["r3.0.2"].includePath_ = pack.versions_["r3.0.2"].includePath_ + "/bsoncxx/v_noabi"
        pack.versions_["r3.0.2"].additionalLdFlags_ = ["-lbsoncxx"]
        pack.addVersion(url, "r3.1.0-rc0", [LibNameVer("mongoc", "1.5.0")])
        pack.versions_["r3.1.0-rc0"].additionalIncludePaths_.append(pack.versions_["r3.1.0-rc0"].includePath_ + "/mongocxx/v_noabi")
        pack.versions_["r3.1.0-rc0"].includePath_ = pack.versions_["r3.1.0-rc0"].includePath_ + "/bsoncxx/v_noabi"
        pack.versions_["r3.1.0-rc0"].additionalLdFlags_ = ["-lbsoncxx"]
        return pack

    def __cppitertools(self):
        url = 'https://github.com/ryanhaining/cppitertools.git'
        name = "cppitertools"
        buildCmd = ""
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git-headeronly", "v0.1")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addHeaderOnlyVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __catch(self):
        url = 'https://github.com/philsquared/Catch.git'
        name = "catch"
        buildCmd = ""
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git-headeronly", "v1.3.3")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addHeaderOnlyVersion(url, ref)
                pack.versions_[ref].includePath_ = os.path.join(joinNameVer(pack.versions_[ref].nameVer_), "single_include")
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __r(self):
        name = "R"
        rHomeLoc = "bin/R RHOME"
        if Utils.isMac():
            rHomeLoc = "R.framework/Resources/bin/R RHOME"
        #&& echo 'install.packages(c(\"gridExtra\", \"ape\", \"ggplot2\", \"seqinr\",\"Rcpp\", \"RInside\",\"devtools\"),
        buildCmd = """./configure --prefix={local_dir} --enable-R-shlib --with-x=no CC={CC} CXX={CXX} OBJC={CC}
                && make -j {num_cores}
                && make install
                && echo '.libPaths(.libPaths()[length(.libPaths()  )] ); install.packages(c(\"tidyverse\", \"gridExtra\", \"ape\", \"ggplot2\", \"seqinr\",\"Rcpp\", \"RInside\"),
                repos=\"http://cran.us.r-project.org\", Ncpus = {num_cores}, lib =.libPaths()[length(.libPaths()  )] )' | $({local_dir}/""" + rHomeLoc + """)/bin/R --slave --vanilla
                """
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "3.4.0")
        pack.versions_["3.4.0"] = CPPLibPackageVersionR("R", "http://baileylab.brown.edu/sourceCodes/R/R-3.4.0.tar.gz", "3.4.0", self.dirMaster_)
        pack.versions_["3.3.3"] = CPPLibPackageVersionR("R", "http://baileylab.brown.edu/sourceCodes/R/R-3.3.3.tar.gz", "3.3.3", self.dirMaster_)
        pack.versions_["3.3.2"] = CPPLibPackageVersionR("R", "http://baileylab.brown.edu/sourceCodes/R/R-3.3.2.tar.gz", "3.3.2", self.dirMaster_)
        pack.versions_["3.3.0"] = CPPLibPackageVersionR("R", "http://baileylab.brown.edu/sourceCodes/R/R-3.3.0.tar.gz", "3.3.0", self.dirMaster_)
        pack.versions_["3.2.4"] = CPPLibPackageVersionR("R", "http://baileylab.brown.edu/sourceCodes/R/R-3.2.4.tar.gz", "3.2.4", self.dirMaster_)
        pack.versions_["3.2.3"] = CPPLibPackageVersionR("R", "http://baileylab.brown.edu/sourceCodes/R/R-3.2.3.tar.gz", "3.2.3", self.dirMaster_)
        pack.versions_["3.2.2"] = CPPLibPackageVersionR("R", "http://baileylab.brown.edu/sourceCodes/R/R-3.2.2.tar.gz", "3.2.2", self.dirMaster_)
        pack.versions_["3.2.1"] = CPPLibPackageVersionR("R", "http://baileylab.brown.edu/sourceCodes/R/R-3.2.1.tar.gz", "3.2.1", self.dirMaster_)
        pack.versions_["3.2.0"] = CPPLibPackageVersionR("R", "http://baileylab.brown.edu/sourceCodes/R/R-3.2.0.tar.gz", "3.2.0", self.dirMaster_)
        pack.versions_["3.1.3"] = CPPLibPackageVersionR("R", "http://baileylab.brown.edu/sourceCodes/R/R-3.1.3.tar.gz", "3.1.3", self.dirMaster_)
        return pack

    def __armadillo(self):
        name = "armadillo"
        buildCmd = "mkdir -p build && cd build && CC={CC} CXX={CXX} cmake -DDETECT_HDF5=false -DCMAKE_CXX_FLAGS=\"-std=c++11\" -DCMAKE_INSTALL_PREFIX:PATH={local_dir} .. && make -j {num_cores} install"
        url = "https://github.com/nickjhathaway/armadillo.git"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "8.200.0")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __libpca(self):
        name = "libpca"
        #the version will get overridden by setting pack.defaultBuildCmd_ latter, but the dependency check needs to install it first
        armPack = self.__armadillo()
        buildCmd = """CC={CC} CXX={CXX} autoreconf -f -i &&  ./configure --prefix {local_dir} && make -j {num_cores} install"""
        defaultArmVer = "8.200.0"
        url = "https://github.com/nickjhathaway/libpca.git"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "1.3.3")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref, [LibNameVer("armadillo", defaultArmVer)] )
                armLdFlags = armPack.versions_[defaultArmVer].getLdFlags(self.dirMaster_.install_dir)
                armIncFlags = armPack.versions_[defaultArmVer].getIncludeFlags(self.dirMaster_.install_dir)
                pack.versions_[ref].cmd_ = "CC={CC} CXX={CXX} LDFLAGS=\"" + armLdFlags + "\" CXXFLAGS=\"" + armIncFlags + "\" autoreconf -f -i &&  " + "CC={CC} CXX={CXX} LDFLAGS=\"" + armLdFlags + "\" CXXFLAGS=\"" + armIncFlags +  "\" ./configure  --prefix {local_dir}  && make -j {num_cores} install"
                pack.versions_[ref].cmd_ = " ".join(pack.versions_[ref].cmd_.split())
                pack.versions_[ref] .altLibName_ = "pca"
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __eigen(self):
        name = "eigen"
        buildCmd = """mkdir build && cd build && CC={CC} CXX={CXX} cmake -DCMAKE_INSTALL_PREFIX={local_dir} .. && make install -j {num_cores}"""
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "3.3.1")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/eigen/eigen-3.3.1.tar.bz2", "3.3.1")
        pack.versions_["3.3.1"].libPath_ = "";
        pack.versions_["3.3.1"].includePath_ = os.path.join(joinNameVer(pack.versions_["3.3.1"].nameVer_), "include", "eigen3")
        return pack

    def __lapack(self):
        name = "lapack"
        buildCmd = """mkdir build && cd build && CC={CC} CXX={CXX} cmake -DCMAKE_INSTALL_PREFIX={local_dir} .. && make install -j {num_cores}"""
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "3.7.0")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/lapack/lapack-3.7.0.tar.gz", "3.7.0")
        return pack


    def __glpk(self):
        name = "glpk"
        buildCmd = """CC={CC} CXX={CXX}  ./configure
            --prefix={local_dir}
            && make -j {num_cores}
            && make -j {num_cores} install"""
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "4.61")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/glpk/glpk-4.61.tar.gz", "4.61")
        return pack

    def __cmake(self):
        name = "cmake"
        buildCmd = """CC={CC} CXX={CXX}  ./configure
            --prefix={local_dir}
            && make -j {num_cores}
            && make -j {num_cores} install"""
        buildCmd = " ".join(buildCmd.split())
        url = "https://github.com/nickjhathaway/cmake.git"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "3.7.2")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __curl(self):
        name = "curl"
        url = "https://github.com/curl/curl.git"
        extraFlags = ""
        #curl library doesn't link to the openssl library at run time as it finds at configure so need to add the following to
        #make the openssl library directory found to be set as run time path
        if Utils.hasProgram("pkg-config"):
            pkgconfgOutput = Utils.runAndCapture("pkg-config --libs openssl")
            if "-L" in pkgconfgOutput:
                pkgconfgOutput_splits = pkgconfgOutput.split()
                extraFlags = "LDFLAGS=" + "\""
                for pkgconfgOutput_split in pkgconfgOutput_splits:
                    if pkgconfgOutput_split.startswith("-L"):
                        extraFlags = extraFlags + " -Wl,-rpath," + pkgconfgOutput_split[2:]
                extraFlags = extraFlags + " $LDFLAGS\""
        buildCmd = """./buildconf && CC={CC} CXX={CXX}  """ + extraFlags + """ ./configure
            --prefix={local_dir}
            && make -j {num_cores}
            && make -j {num_cores} install"""
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "curl-7_56_1")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __atlas(self):
        name = "atlas"
        buildCmd = """mkdir build && cd build && CC={CC} CXX={CXX}  ../configure
            --prefix={local_dir}
            && make -j {num_cores}
            && make -j {num_cores} install"""
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "3.10.3")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/atlas/atlas3.10.3.tar.gz", "3.10.3")
        return pack

    def __muscle(self):
        name = "muscle"
        buildCmd = "CC={CC} CXX={CXX} make -j {num_cores} && mkdir -p {local_dir}/bin && cp muscle {local_dir}/bin/"
        url = "https://github.com/nickjhathaway/muscle.git"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "3.8.31")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __adapterremoval(self):
        name = "adapterremoval"
        buildCmd = "CC={CC} CXX={CXX} make -j {num_cores} && make -j {num_cores} install PREFIX={local_dir}"
        url = "https://github.com/MikkelSchubert/adapterremoval.git"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v2.2.2")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack


    def __bowtie2(self):
        name = "bowtie2"
        url = "https://github.com/BenLangmead/bowtie2.git"
        buildCmd = "CC={CC} CXX={CXX} make -j {num_cores} && mkdir -p {local_dir}/bin && cp -r bowtie2* {local_dir}/bin/"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v2.3.4.1")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __flash(self):
        name = "flash"
        buildCmd = "CC={CC} CXX={CXX} ZLIBADDFLAGS make -j {num_cores} && mkdir -p {local_dir}/bin && cp flash {local_dir}/bin/"
        url = "https://github.com/nickjhathaway/flash.git"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "1.3")
        defaultZlibVersion = "1.3";
        zlibPack = self.__zlib()
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
                zlibLdFlags = zlibPack.versions_[defaultZlibVersion].getLdFlags(self.dirMaster_.install_dir)
                zlibIncFlags = zlibPack.versions_[defaultZlibVersion].getIncludeFlags(self.dirMaster_.install_dir)
                zlibAddFlags = "LDFLAGS=\""+ zlibLdFlags + "\" CXXFLAGS=\""+ zlibIncFlags + "\""
                pack.versions_[ref].cmd_ = buildCmd.replace("ZLIBADDFLAGS", zlibAddFlags)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack


    def __pigz(self):
        name = "pigz"
        buildCmd = "CC={CC} CXX={CXX} make -j {num_cores} && mkdir -p {local_dir}/bin && cp pigz unpigz {local_dir}/bin/"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "2.3.4")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/pigz/pigz-2.3.4.tar.gz", "2.3.4")
        return pack

    def __lastz(self):
        name = "lastz"
        buildCmd = "sed -i.bak 's/-Werror//g' src/Makefile && CC={CC} CXX={CXX} make -j {num_cores} && mkdir -p {local_dir}/bin && cp src/lastz src/lastz_D {local_dir}/bin/"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "1.03.73")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/lastz/lastz-1.03.73.tar.gz", "1.03.73")
        return pack

    def __samtools(self):
        name = "samtools"
        url = "https://github.com/samtools/samtools.git"
        buildCmd = "git clone https://github.com/samtools/htslib.git && cd htslib && git checkout SAMVERSION && CC={CC} CXX={CXX} autoheader && autoconf  && cd .. && CC={CC} CXX={CXX} autoheader && autoconf &&  ./configure --prefix={local_dir} && make -j {num_cores} && make install "
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "1.8")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
                pack.versions_[ref].cmd_ = buildCmd.replace("SAMVERSION", ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __bcftools(self):
        name = "bcftools"
        buildCmd = "CC={CC} CXX={CXX} && make prefix={local_dir} -j {num_cores} && make prefix={local_dir} install "
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "1.3.1")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/bcftools/bcftools-1.3.1.tar.bz2", "1.3.1")
        return pack

    def __hts(self):
        name = "hts"
        url = "https://github.com/samtools/htslib.git"
        #buildCmd = "CC={CC} CXX={CXX} && autoheader && autoconf && ./configure --prefix={local_dir} && make -j {num_cores} && make install -j {num_cores}"
        buildCmd = "CC={CC} CXX={CXX} && autoreconf -if && ./configure --prefix={local_dir} && make -j {num_cores} && make install -j {num_cores}"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "1.3.1")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
                pack.versions_[ref].additionalLdFlags_ = ["-lz -lm -lpthread"]
                #pack.versions_[ref].additionalLdFlags_ = ["-ldeflate -llzma -lbz2 -lz -lm  -lcurl -lcrypto"]
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __zlibng(self):
        name = "zlib-ng"
        url = "https://github.com/Dead2/zlib-ng"
        buildCmd = "CC={CC} CXX={CXX} && ./configure --prefix={local_dir} && make -j {num_cores} && make install -j {num_cores}"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "develop")

        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
                pack.versions_[ref].altLibName_ = "z"
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __openblas(self):
        name = "openblas"
        url = "https://github.com/xianyi/OpenBLAS.git"
        buildCmd = "CC={CC} CXX={CXX} && make PREFIX={local_dir} -j {num_cores} && make install PREFIX={local_dir} -j {num_cores}"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "develop")

        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __unqlite(self):
        name = "unqlite"
        url = "https://github.com/symisc/unqlite.git"
        buildCmd = "mkdir -p build && cd build && CC={CC} CXX={CXX} cmake -DCMAKE_INSTALL_PREFIX:PATH={local_dir} .. && make UNQLITE_ENABLE_THREADS=true -j {num_cores} install"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v1.1.9")

        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack



    def __restbed(self):
        name = "restbed"
        url = "https://github.com/Corvusoft/restbed.git"
        if not Utils.isMac():
            buildCmd = """git submodule init && git submodule update && sed -i 's/CMAKE_CXX_FLAGS}} -stdlib=libc++/CMAKE_CXX_FLAGS}}/g' cmake/build_configuration.cmake && mkdir build && cd build && CC={CC} CXX={CXX} cmake -DBUILD_TESTS=NO -DBUILD_EXAMPLES=NO -DBUILD_SSL=NO -DBUILD_SHARED=YES -DCMAKE_INSTALL_PREFIX={local_dir} .. && make install -j {num_cores}"""
        else:
            buildCmd = """git submodule init && git submodule update &&                                                                                                    mkdir build && cd build && CC={CC} CXX={CXX} cmake -DBUILD_TESTS=NO -DBUILD_EXAMPLES=NO -DBUILD_SSL=NO -DBUILD_SHARED=YES -DCMAKE_INSTALL_PREFIX={local_dir} .. && make install -j {num_cores}"""

        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "4.0")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
                pack.versions_[ref].libPath_ = pack.versions_[ref].libPath_ + "rary"
                allFloats = re.findall(r"[+-]? *(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", ref)
                if len(allFloats) >= 1 and float(allFloats[0]) >= 4.5:
                    pack.versions_[ref].cmd_ = """git submodule init && git submodule update &&                                                                                                    mkdir build && cd build && CC={CC} CXX={CXX} cmake -DBUILD_TESTS=NO -DBUILD_EXAMPLES=NO -DBUILD_SSL=NO -DBUILD_SHARED=YES -DCMAKE_INSTALL_PREFIX={local_dir} .. && make install -j {num_cores}"""
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        #pack.addVersion("https://github.com/Corvusoft/restbed.git", "4.0")
        #pack.versions_["4.0"].additionalLdFlags_ = ["-lz -lm -lpthread"]
        return pack



    #'''
    #def __mlpack(self):
    #    url = "http://www.mlpack.org/files/mlpack-1.0.8.tar.gz"
    #    armadillo_dir = Utils.shellquote(i.local_dir).replace("mlpack", "armadillo")
    #    boost_dir = Utils.shellquote(i.local_dir).replace("mlpack", "boost")
    #    cmd = """
    #    mkdir -p build
    #    && cd build
    #    && CC={CC} CXX={CXX} cmake -D DEBUG=OFF -D PROFILE=OFF
    #     -D ARMADILLO_LIBRARY={armadillo_dir}/lib/libarmadillo.so.4.0.2
    #     -D ARMADILLO_INCLUDE_DIR={armadillo_dir}/include/
    #     -D CMAKE_INSTALL_PREFIX:PATH={local_dir} ..
    #     -DBoost_NO_SYSTEM_PATHS=TRUE -DBOOST_INCLUDEDIR={boost}/include/ -DBOOST_LIBRARYDIR={boost}/lib/
    #    && make -j {num_cores} install
    #    """.format(local_dir=Utils.shellquote(i.local_dir),
    #       armadillo_dir=armadillo_dir,
    #       num_cores=self.num_cores(),
    #       boost=boost_dir, CC=self.CC, CXX=self.CXX)
    #    cmd = " ".join(cmd.split('\n'))
    #    return self.__package_dirs(url, "mlpack")

    #def __liblinear(self):
    #    name = "liblinear"
    #    url = "http://www.csie.ntu.edu.tw/~cjlin/liblinear/oldfiles/liblinear-1.94.tar.gz"
    #    cmd = """
    #        perl -p -i -e 's/if\(check_probability_model/if\(1 || check_probability_model/' linear.cpp &&
    #        make &&
    #        mkdir -p {local_dir} &&
    #        cp predict train {local_dir} &&
    #        make lib &&
    #        cp linear.h liblinear.so.1 README {local_dir} &&
    #        ln -s {local_dir}/liblinear.so.1 {local_dir}/liblinear.so
    #        """.format(local_dir=Utils.shellquote(i.local_dir))
    #    cmd = " ".join(cmd.split())
    #    return self.__package_dirs(url, "liblinear")
    #'''

    def __magic(self):
        name = "magic"
        buildCmd = """./configure CC={CC} CXX={CXX} --disable-dependency-tracking  --disable-silent-rules
            --prefix={local_dir}
            --enable-fsect-man5  --enable-static
            && make -j {num_cores}
            && make -j {num_cores} install"""
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "5.25")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/libmagic/file-5.25.tar.gz", "5.25")
        return pack

    def __zlib(self):
        url = 'https://github.com/nickjhathaway/zlib.git'
        name = "zlib"
        buildCmd = """CC={CC} CXX={CXX}  ./configure
           --prefix={local_dir}
           && make -j {num_cores}
           && make -j {num_cores} install"""
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "1.3")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
                pack.versions_[ref].altLibName_ = "z"
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __mathgl(self):
        name = "mathgl"
        buildCmd = ""
        if "clang" in self.args.CC:
            buildCmd = """mkdir -p build && cd build && CC={CC} CXX={CXX} cmake -DCMAKE_INSTALL_PREFIX:PATH={local_dir} -Denable-pthread=ON -Denable-openmp=OFF ..
            && make -j {num_cores} install"""
        else:
            buildCmd = """mkdir -p build && cd build && CC={CC} CXX={CXX} cmake -DCMAKE_INSTALL_PREFIX:PATH={local_dir}  ..
            && make -j {num_cores} install"""
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "2.2.1")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/mathgl/mathgl-2.2.1.tar.gz", "2.2.1")
        pack.versions_["2.2.1"].includePath_ = os.path.join(pack.versions_["2.2.1"].includePath_,"mgl2")
        pack.versions_["2.2.1"].altLibName_ = "mgl"
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/mathgl/mathgl-2.3.4.tar.gz", "2.3.4")
        pack.versions_["2.3.4"].includePath_ = os.path.join(pack.versions_["2.3.4"].includePath_,"mgl2")
        pack.versions_["2.3.4"].altLibName_ = "mgl"
        return pack

    def __cppcms(self):
        name = "cppcms"
        buildCmd = "mkdir -p build && cd build && CC={CC} CXX={CXX} cmake -DCMAKE_INSTALL_PREFIX:PATH={local_dir} .. && make -j {num_cores} install"
        if(sys.platform == "darwin"):
            buildCmd += " && install_name_tool -change libbooster.0.dylib {local_dir}/lib/libbooster.0.dylib {local_dir}/lib/libcppcms.1.dylib"
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "1.0.5")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/cppcms/cppcms-1.0.5.tar.bz2", "1.0.5")
        pack.versions_["1.0.5"].additionalLdFlags_ = ["-lbooster"]
        return pack

    def __dlib(self):
        name = "dlib"
        buildCmd = "mkdir {local_dir} && cp -a * {local_dir}/"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "18.7")
        pack.addVersion("http://freefr.dl.sourceforge.net/project/dclib/dlib/v18.7/dlib-18.7.tar.bz2", "18.7")
        pack.versions_["18.7"].includePath_ = joinNameVer(pack.versions_["18.7"].nameVer_)
        pack.versions_["18.7"].libPath_ = ""
        return pack

    def __libsvm(self):
        name = "libsvm"
        buildCmd = "make && make lib && mkdir -p {local_dir} && cp -a * {local_dir}"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "3.18")
        pack.addVersion("http://www.csie.ntu.edu.tw/~cjlin/libsvm/oldfiles/libsvm-3.18.tar.gz", "3.18")
        pack.versions_["3.18"].includePath_ = joinNameVer(pack.versions_["3.18"].nameVer_)
        pack.versions_["3.18"].libPath_ = ""
        return pack

    def __cppprogutils(self):
        url = 'https://github.com/bailey-lab/cppprogutils.git'
        name = "cppprogutils"
        buildCmd = ""
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git-headeronly", "v2.0.0")
        #pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addHeaderOnlyVersion(url, ref)
                pack.versions_[ref].additionalLdFlags_ = ["-lpthread"]
                pack.versions_[ref].includePath_ = os.path.join(name, ref, name)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __njhseq(self):
        url = "https://github.com/nickjhathaway/njhseq.git"
        name = "njhseq"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v2.3.0")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
                needCurl = False
                if not ref.startswith("v"):
                    needCurl = True
                else:
                    major = int(ref[1]);
                    minor = int(ref[3]);
                    #patch = int(ref[5]);
                    if not major >= 3 and not (major == 2 and minor > 4):
                        needCurl = True
                if "develop" in ref:
                    needCurl = False
                if needCurl:
                    pack.versions_[ref].additionalLdFlags_ = ["-lcurl"]

            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __twobit(self):
        url = "https://github.com/nickjhathaway/TwoBit.git"
        name = "TwoBit"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v2.0.1")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __sharedMutex(self):
        url = "https://github.com/nickjhathaway/cpp_shared_mutex.git"
        name = "sharedMutex"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v0.3")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __bhtsne(self):
        url = "git@github.com:umass-bib/bhtsne.git"
        name = "bhtsne"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v0.3")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __SeekDeep(self):
        url = "https://github.com/bailey-lab/SeekDeep.git"
        name = "SeekDeep"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v2.3.3")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __elucidatorlab(self):
        url = "git@github.com:nickjhathaway/elucidatorlab.git"
        name = "elucidatorlab"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v2.3.3")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __elucidator(self):
        url = "https://github.com/nickjhathaway/elucidator.git"
        name = "elucidator"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v2.3.3")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __pathweaver(self):
        url = "https://github.com/nickjhathaway/PathWeaver.git"
        name = "PathWeaver"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v2.3.3")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack



    def __seqserver(self):
        url = "https://github.com/nickjhathaway/seqServer.git"
        name = "seqServer"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v1.3.1")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __MIPWrangler(self):
        url = "https://github.com/bailey-lab/MIPWrangler.git"
        name = "MIPWrangler"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "develop")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __njhRInside(self):
        url = "https://github.com/nickjhathaway/njhRInside.git"
        name = "njhRInside"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "1.1.1")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __njhcpp(self):
        url = "https://github.com/nickjhathaway/njhcpp.git"
        name = "njhcpp"
        buildCmd = self.__njhProjectBuildCmd()
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "v2.3.0")
        pack.njhProject_ = True
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                    pack = pickle.load(inputPkl)
                    pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
                #pack.versions_[ref].additionalLdFlags_ = ["-lpthread", "-lz"]
                pack.versions_[ref].additionalLdFlags_ = ["-lpthread"]
                if not Utils.isMac():
                    pack.versions_[ref].additionalLdFlags_.append("-lrt")
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __boost(self):
        name = "boost"
        buildCmd = ""
        boostLibs = "filesystem,system,math"
        if Utils.isMac():
            #print "here"
            setUpDir = os.path.dirname(os.path.abspath(__file__))
            gccJamLoc =  os.path.join(setUpDir, "scripts/etc/boost/gcc.jam")
            gccJamOutLoc = "{build_sub_dir}/tools/build/src/tools/gcc.jam"
            #print gccJamLoc
            #print gccJamOutLoc

            installNameToolCmd  = """
            && if [ ! -z $(otool -L {local_dir}/lib/libboost_filesystem.dylib | egrep -o "\\S+libboost_system.dylib") ]; then install_name_tool -change $(otool -L {local_dir}/lib/libboost_filesystem.dylib | egrep -o "\\S+libboost_system.dylib") {local_dir}/lib/libboost_system.dylib {local_dir}/lib/libboost_filesystem.dylib ; fi
            && install_name_tool -id {local_dir}/lib/libboost_filesystem.dylib {local_dir}/lib/libboost_filesystem.dylib
            && install_name_tool -id {local_dir}/lib/libboost_system.dylib {local_dir}/lib/libboost_system.dylib
            """
        if self.args.clang:
            if Utils.isMac():
                buildCmd = """./bootstrap.sh --with-toolset=clang --prefix={local_dir} --with-libraries=""" + boostLibs + """
                  &&  ./b2 -d 0  toolset=clang cxxflags=\"-stdlib=libc++ -std=c++17\" linkflags=\"-stdlib=libc++\" -j {num_cores} install
                  """ + installNameToolCmd
            else:
                buildCmd = """ln -s $(for x in $(which -a {CC}); do echo $(realpath $x); done | egrep clang | head -1) clang && PATH=$(realpath .):$PATH && ln -s $(for x in $(which -a {CXX}); do echo $(realpath $x); done | egrep clang | head -1) clang++ && ./bootstrap.sh --with-toolset=clang --prefix={local_dir}  --with-libraries=""" + boostLibs + """ &&  ./b2 -d 0 toolset=clang cxxflags=\"-std=c++17\" -j {num_cores} install && rm clang && rm clang++"""
        elif "g++" in self.args.CXX:
            if "-" in self.args.CXX:
                gccVer = self.args.CXX[(self.args.CXX.find("-") + 1):]
                if Utils.isMac():
                    buildCmd = "cp " + gccJamLoc + "  " + gccJamOutLoc + """ && ./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && echo "using gcc : """ + str(gccVer) + """ : {CXX} : <linker-type>darwin ;" >> tools/build/src/user-config.jam
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" --toolset=gcc -""" + str(gccVer) +  """ -j {num_cores} install
                     """ + installNameToolCmd
                else:
                    buildCmd = """./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && echo "using gcc : """ + str(gccVer) + """ : {CXX} ;" >> tools/build/src/user-config.jam
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" --toolset=gcc -""" + str(gccVer) +  """ -j {num_cores} install
                     """
            else:
                if Utils.isMac():
                    buildCmd = "cp " + gccJamLoc + "  " + gccJamOutLoc + """ && echo "using gcc :  : g++ : <linker-type>darwin ;" >> tools/build/src/user-config.jam
                     && ./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" --toolset=gcc  -j {num_cores} install
                     """ + installNameToolCmd
                else:
                    buildCmd = """./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" --toolset=gcc  -j {num_cores} install
                     """
        buildCmd = " ".join(buildCmd.split())
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "file", "1_60_0")
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/boost/boost_1_58_0.tar.bz2", "1_58_0")
        pack.versions_["1_58_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_58_0"].libName_ = ""
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/boost/boost_1_59_0.tar.bz2", "1_59_0")
        pack.versions_["1_59_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_59_0"].libName_ = ""
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/boost/boost_1_60_0.tar.bz2", "1_60_0")
        pack.versions_["1_60_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_60_0"].libName_ = ""
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/boost/boost_1_62_0.tar.bz2", "1_62_0")
        pack.versions_["1_62_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_62_0"].libName_ = ""
        pack.addVersion("http://baileylab.brown.edu/sourceCodes/boost/boost_1_70_0.tar.bz2", "1_70_0")
        pack.versions_["1_70_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_70_0"].libName_ = ""
        pack.addVersion("https://boostorg.jfrog.io/artifactory/main/release/1.74.0/source/boost_1_74_0.tar.bz2", "1_74_0")
        pack.versions_["1_74_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_74_0"].libName_ = ""
        pack.addVersion("https://boostorg.jfrog.io/artifactory/main/release/1.75.0/source/boost_1_75_0.tar.bz2", "1_75_0")
        pack.versions_["1_75_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_75_0"].libName_ = ""
        pack.addVersion("https://boostorg.jfrog.io/artifactory/main/release/1.76.0/source/boost_1_76_0.tar.bz2", "1_76_0")
        pack.versions_["1_76_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_76_0"].libName_ = ""
        pack.addVersion("https://boostorg.jfrog.io/artifactory/main/release/1.77.0/source/boost_1_77_0.tar.bz2", "1_77_0")
        pack.versions_["1_77_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_77_0"].libName_ = ""
        pack.addVersion("https://boostorg.jfrog.io/artifactory/main/release/1.78.0/source/boost_1_78_0.tar.bz2", "1_78_0")
        pack.versions_["1_78_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_78_0"].libName_ = ""
        pack.addVersion("https://boostorg.jfrog.io/artifactory/main/release/1.79.0/source/boost_1_79_0.tar.bz2", "1_79_0")
        pack.versions_["1_79_0"].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
        pack.versions_["1_79_0"].libName_ = ""
        return pack

    def __boost_filesystem(self):
        name = "boost_filesystem"
        buildCmd = ""
        boostLibs = "filesystem,system"
        if Utils.isMac():
            #print "here"
            setUpDir = os.path.dirname(os.path.abspath(__file__))
            gccJamLoc =  os.path.join(setUpDir, "scripts/etc/boost/gcc.jam")
            gccJamOutLoc = "{build_sub_dir}/tools/build/src/tools/gcc.jam"
            #print gccJamLoc
            #print gccJamOutLoc
            installNameToolCmd  = """
            && if [ ! -z $(otool -L {local_dir}/lib/libboost_filesystem.dylib | egrep -o "\\S+libboost_system.dylib") ]; then install_name_tool -change $(otool -L {local_dir}/lib/libboost_filesystem.dylib | egrep -o "\\S+libboost_system.dylib") {local_dir}/lib/libboost_system.dylib {local_dir}/lib/libboost_filesystem.dylib ; fi
            && install_name_tool -id {local_dir}/lib/libboost_filesystem.dylib {local_dir}/lib/libboost_filesystem.dylib
            && install_name_tool -id {local_dir}/lib/libboost_system.dylib {local_dir}/lib/libboost_system.dylib
            && if [ ! -z $(otool -L {local_dir}/lib/libboost_filesystem.dylib | egrep -o "\\S+libboost_atomic.dylib") ]; then install_name_tool -change $(otool -L {local_dir}/lib/libboost_filesystem.dylib | egrep -o "\\S+libboost_atomic.dylib") {local_dir}/lib/libboost_atomic.dylib {local_dir}/lib/libboost_filesystem.dylib ; fi
            && if [ -f {local_dir}/lib/libboost_atomic.dylib ]; then install_name_tool -id {local_dir}/lib/libboost_atomic.dylib {local_dir}/lib/libboost_atomic.dylib; fi
            """
            #print(installNameToolCmd)
        if self.args.clang:
            if Utils.isMac():
                buildCmd = """./bootstrap.sh --with-toolset=clang --prefix={local_dir} --with-libraries=""" + boostLibs + """
                  &&  ./b2 -d 0 toolset=clang cxxflags=\"-stdlib=libc++ -std=c++17\" linkflags=\"-stdlib=libc++\" -j {num_cores} install
                  """ + installNameToolCmd
            else:
                buildCmd = """ln -s $(for x in $(which -a {CC}); do echo $(realpath $x); done | egrep clang | head -1) clang && PATH=$(realpath .):$PATH && ln -s $(for x in $(which -a {CXX}); do echo $(realpath $x); done | egrep clang | head -1) clang++ && ./bootstrap.sh --with-toolset=clang --prefix={local_dir}  --with-libraries=""" + boostLibs + """ &&  ./b2 -d 0 toolset=clang cxxflags=\"-std=c++17\" -j {num_cores} install && rm clang && rm clang++"""
        elif "g++" in self.args.CXX:
            if "-" in self.args.CXX:
                gccVer = self.args.CXX[(self.args.CXX.find("-") + 1):]
                if Utils.isMac():
                    buildCmd = "cp " + gccJamLoc + "  " + gccJamOutLoc + """ && ./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && echo "using gcc : """ + str(gccVer) + """ : {CXX} : <linker-type>darwin ;" >> tools/build/src/user-config.jam
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" linkflags=\"-Wl,-rpath,{local_dir}/lib\" --toolset=gcc -""" + str(gccVer) +  """ -j {num_cores} install
                     """ + installNameToolCmd
                else:
                    buildCmd = """./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && echo "using gcc : """ + str(gccVer) + """ : {CXX} ;" >> tools/build/src/user-config.jam
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" linkflags=\"-Wl,-rpath,{local_dir}/lib\" --toolset=gcc -""" + str(gccVer) +  """ -j {num_cores} install
                     """
            else:
                if Utils.isMac():
                    buildCmd = "cp " + gccJamLoc + "  " + gccJamOutLoc + """ && echo "using gcc :  : g++ : <linker-type>darwin ;" >> tools/build/src/user-config.jam
                     && ./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" linkflags=\"-Wl,-rpath,{local_dir}/lib\" --toolset=gcc  -j {num_cores} install
                     """ + installNameToolCmd
                else:
                    buildCmd = """./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" linkflags=\"-Wl,-rpath,{local_dir}/lib\" --toolset=gcc  -j {num_cores} install
                     """
        buildCmd = " ".join(buildCmd.split())
        url = "https://github.com/nickjhathaway/boost_filesystem.git"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "1_60_0")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
                pack.versions_[ref].additionalLdFlags_ = ["-lboost_system", "-lboost_filesystem"]
                pack.versions_[ref].libName_ = ""
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def __boost_math(self):
        name = "boost_math"
        buildCmd = ""
        boostLibs = "math"
        if Utils.isMac():
            #print "here"
            setUpDir = os.path.dirname(os.path.abspath(__file__))
            gccJamLoc =  os.path.join(setUpDir, "scripts/etc/boost/gcc.jam")
            gccJamOutLoc = "{build_sub_dir}/tools/build/src/tools/gcc.jam"
            #print gccJamLoc
            #print gccJamOutLoc
            installNameToolCmd  = """
            && install_name_tool -id {local_dir}/lib/libboost_math_c99.dylib {local_dir}/lib/libboost_math_c99.dylib
            && install_name_tool -id {local_dir}/lib/libboost_math_c99f.dylib {local_dir}/lib/libboost_math_c99f.dylib
            && install_name_tool -id {local_dir}/lib/libboost_math_c99l.dylib {local_dir}/lib/libboost_math_c99l.dylib
            && install_name_tool -id {local_dir}/lib/libboost_math_tr1.dylib {local_dir}/lib/libboost_math_tr1.dylib
            && install_name_tool -id {local_dir}/lib/libboost_math_tr1f.dylib {local_dir}/lib/libboost_math_tr1f.dylib
            && install_name_tool -id {local_dir}/lib/libboost_math_tr1l.dylib {local_dir}/lib/libboost_math_tr1l.dylib
            """
            #print(installNameToolCmd)
        if self.args.clang:
            if Utils.isMac():
                buildCmd = """./bootstrap.sh --with-toolset=clang --prefix={local_dir} --with-libraries=""" + boostLibs + """
                  &&  ./b2 -d 0 toolset=clang cxxflags=\"-stdlib=libc++ -std=c++17\" linkflags=\"-stdlib=libc++\" -j {num_cores} install
                  """ + installNameToolCmd
            else:
                buildCmd = """ln -s $(for x in $(which -a {CC}); do echo $(realpath $x); done | egrep clang | head -1) clang && PATH=$(realpath .):$PATH && ln -s $(for x in $(which -a {CXX}); do echo $(realpath $x); done | egrep clang | head -1) clang++ && ./bootstrap.sh --with-toolset=clang --prefix={local_dir}  --with-libraries=""" + boostLibs + """ &&  ./b2 -d 0 toolset=clang cxxflags=\"-std=c++17\" -j {num_cores} install && rm clang && rm clang++"""
        elif "g++" in self.args.CXX:
            if "-" in self.args.CXX:
                gccVer = self.args.CXX[(self.args.CXX.find("-") + 1):]
                if Utils.isMac():
                    buildCmd = "cp " + gccJamLoc + "  " + gccJamOutLoc + """ && ./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && echo "using gcc : """ + str(gccVer) + """ : {CXX} : <linker-type>darwin ;" >> tools/build/src/user-config.jam
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" --toolset=gcc -""" + str(gccVer) +  """ -j {num_cores} install
                     """ + installNameToolCmd
                else:
                    buildCmd = """./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && echo "using gcc : """ + str(gccVer) + """ : {CXX} ;" >> tools/build/src/user-config.jam
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" --toolset=gcc -""" + str(gccVer) +  """ -j {num_cores} install
                     """
            else:
                if Utils.isMac():
                    buildCmd = "cp " + gccJamLoc + "  " + gccJamOutLoc + """ && echo "using gcc :  : g++ : <linker-type>darwin ;" >> tools/build/src/user-config.jam
                     && ./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" --toolset=gcc  -j {num_cores} install
                     """ + installNameToolCmd
                else:
                    buildCmd = """./bootstrap.sh --with-toolset=gcc --prefix={local_dir} --with-libraries=""" + boostLibs + """
                     && ./b2 -d 0 cxxflags=\"-std=c++17\" --toolset=gcc  -j {num_cores} install
                     """
        buildCmd = " ".join(buildCmd.split())
        url = "https://github.com/nickjhathaway/boost_math.git"
        pack = CPPLibPackage(name, buildCmd, self.dirMaster_, "git", "1_75_0")
        if self.args.noInternet:
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        elif os.path.exists(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl')):
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'rb') as inputPkl:
                pack = pickle.load(inputPkl)
                pack.defaultBuildCmd_ = buildCmd
        else:
            refs = pack.getGitRefs(url)
            for ref in [b.replace("/", "__") for b in refs.branches] + refs.tags:
                pack.addVersion(url, ref)
                #pack.versions_[ref].additionalLdFlags_ = ["-lboost_math"]
                pack.versions_[ref].libName_ = ""
            Utils.mkdir(os.path.join(self.dirMaster_.cache_dir, name))
            with open(os.path.join(self.dirMaster_.cache_dir, name, name + '.pkl'), 'wb') as output:
                pickle.dump(pack, output, pickle.HIGHEST_PROTOCOL)
        return pack

    def getPackagesNames(self):
        return sorted(self.packages_.keys())

    def checkForPackVer(self, packVer):
        if packVer.name not in self.packages_:
            raise Exception("Lib " + packVer.name + " not found in libs, options are " + ", ".join(self.getPackagesNames()))
        else:
            if packVer.version.replace("/", "__") not in self.packages_[packVer.name].versions_:
                raise Exception("Version " + packVer.version + " for lib " \
                                + packVer.name + " not found in available versions, options are " \
                                + ", ".join(self.packages_[packVer.name].getVersions()))
        return True

    def getLdFlags(self, packVer):
        self.checkForPackVer(packVer)
        return self.packages_[packVer.name].versions_[packVer.version].getLdFlags(self.dirMaster_.install_dir)

    def getIncludeFlags(self, packVer):
        self.checkForPackVer(packVer)
        return self.packages_[packVer.name].versions_[packVer.version].getIncludeFlags(self.dirMaster_.install_dir)

    def writeMakefile(self, packVers, filename, overwrite = False, append = False):
        if os.path.exists(filename) and not overwrite and not append:
            raise Exception("File: " + str(filename) + " already exists, use --overWrite to overwrite it")
        elif os.path.exists(filename) and overwrite:
            os.remove(filename)
            self.writeMakefile(packVers, filename, overwrite, append)
        elif os.path.exists(filename) and append:
            packsInFile = self.getPackagesInMakefileCommon(filename);
            with open(filename, "a") as f:
                for packVer in packVers:
                    pack = self.package(packVer.name)
                    if packVer.name in packsInFile:
                        if packsInFile[packVer.name] == packVer.version:
                            continue
                        else:
                            raise Exception("Package " + packVer.name + " already in " + filename + " but with a different version, present: " + packsInFile[packVer.name] + ", adding: " + packVer.version)
                    #if njh project, add the flags of it's dependencies
                    if pack.njhProject_:
                        cmd = "./setup.py --compfile compfile.mk --numCores 1 --append --outMakefile {makefileCommon}".format(makefileCommon = os.path.abspath(filename))
                        buildSubDir = pack.getBuildSubDir(packVer.version)
                        Utils.run_in_dir(cmd, buildSubDir)
                    pvIncFlags = self.getIncludeFlags(packVer)
                    if "" != pvIncFlags:
                        f.write("#" + packVer.name + ":" + packVer.version + " CXXFLAGS\n")
                        f.write("COMLIBS += " + pvIncFlags + "\n")
                    pvLdFlags = self.getLdFlags(packVer)
                    if "" != pvLdFlags:
                        f.write("#" + packVer.name + ":" + packVer.version + " LDFLAGS\n")
                        f.write("LD_FLAGS += " + pvLdFlags + "\n")
                    f.write("\n")
                    f.flush()
        else:
            with open(filename, "a") as f:
                f.write("#Utils\n")
                f.write("# from http://stackoverflow.com/a/18258352\n")
                f.write("rwildcard=$(foreach d,$(wildcard $1*),$(call rwildcard,$d/,$2) $(filter $(subst *,%,$2),$d))\n")
                f.write("\n")
                f.write("#Default CXXFLAGS\n")
                f.write("COMLIBS += " + self.getDefaultIncludeFlags() + "\n")
                dLdFlags = self.getDefaultLDFlags()
                if "" != dLdFlags:
                    f.write("#Default LDFLAGS\n")
                    f.write("LD_FLAGS += " + dLdFlags + "\n")
                f.write("\n")
                f.flush()
                for packVer in packVers:
                    pack = self.package(packVer.name)
                    #if njh project, add the flags of it's dependencies
                    if pack.njhProject_:
                            cmd = "./setup.py --compfile compfile.mk --numCores 1 --append --outMakefile {makefileCommon}".format(makefileCommon = os.path.abspath(filename))
                            buildSubDir = pack.getBuildSubDir(packVer.version)
                            Utils.run_in_dir(cmd, buildSubDir)
                    pvIncFlags = self.getIncludeFlags(packVer)
                    if "" != pvIncFlags:
                        f.write("#" + packVer.name + ":" + packVer.version + " CXXFLAGS\n")
                        f.write("COMLIBS += " + pvIncFlags + "\n")
                    pvLdFlags = self.getLdFlags(packVer)
                    if "" != pvLdFlags:
                        f.write("#" + packVer.name + ":" + packVer.version + " LDFLAGS\n")
                        f.write("LD_FLAGS += " + pvLdFlags + "\n")
                    f.write("\n")
                    f.flush()

    def addPackage(self, packVers, packVer):
        if hasattr(packVer, "commit"):
            packVer = LibNameVerCommit(packVer.name, packVer.version.replace("/", "__"), packVer.commit)
        else:
            packVer = LibNameVer(packVer.name, packVer.version.replace("/", "__"))
        if self.checkForPackVer(packVer):
            pack = self.package(packVer.name)
            for dep in pack.versions_[packVer.version].depends_:
                self.setUpPackagesNeeded([str(dep.name).lower()])
                if hasattr(dep, "commit"):
                    self.addPackage(packVers, LibNameVerCommit(str(dep.name).lower(), dep.version, dep.commit))
                else:
                    self.addPackage(packVers, LibNameVer(str(dep.name).lower(), dep.version))
            found = False
            for otherPackVer in packVers:
                if otherPackVer.name == packVer.name:
                    if otherPackVer.version != packVer.version:
                        raise Exception("Version conflict for " + packVer.name + " already have " + otherPackVer.version + " and adding: " + packVer.version)
                    elif hasattr(otherPackVer, "commit") and hasattr(packVer, "commit") and otherPackVer.commit != packVer.commit:
                        raise Exception("Commit conflict for " + str(packVer.name) + " version: " + str(packVer.version) + " already have " + str(otherPackVer.commit) +  " and adding: " + str(packVer.commit))
                    else:
                        found = True
            if not found:
                packVers.append(packVer)

    @staticmethod
    def getPackagesInMakefileCommon(makefileFnp):
        packagesAlready = {}
        with open(makefileFnp, "r") as makefile:
            for line in makefile:
                if ':' in line and line.startswith("#") and "CXXFLAGS" in line:
                    toks = line[1:].split()
                    firstToks = toks[0].split(":")
                    packagesAlready[firstToks[0]] = firstToks[1]
        return packagesAlready

    def isInstalled(self, packVer):
        if os.path.exists(os.path.join(self.dirMaster_.install_dir, joinNameVer(packVer))):
            return True
        else:
            return False

    def getDefaultIncludeFlags(self):
        return "-I./src/"

    def getDefaultLDFlags(self):
        ret = ""
        if Utils.isMac():
            #for dylib path fixing in macs, this gets rid of the name_size limit, which why the hell is there a name size limit
            ret = ret + "-headerpad_max_install_names"
        return ret

    def __njhProjectBuildCmdOld(self):
        cmd = """
        ./configure.py -CC {CC} -CXX {CXX} -externalLibDir {external} -prefix {localTop}
        && ./setup.py --compfile compfile.mk --numCores {num_cores}
        && make -j {num_cores} && make install"""
        cmd = " ".join(cmd.split())
        return cmd

    def __njhProjectBuildCmd(self):
        cmd = """
         ./configure.py -CC {CC} -CXX {CXX} -externalLibDir {external} -prefix $(dirname {local_dir}) """
        if self.args.noInternet:
            cmd = cmd + """&& ./setup.py --compfile compfile.mk --numCores {num_cores}
             --outMakefile makefile-common.mk --overWrite --noInternet """
        else:
            cmd = cmd + """&& ./setup.py --compfile compfile.mk --numCores {num_cores}
             --outMakefile makefile-common.mk --overWrite """
        cmd = cmd + """&& make clean
        && make -j {num_cores} && make install"""
        cmd = " ".join(cmd.split())
        return cmd



class Setup:
    def __init__(self, args):
        self.extDirLoc = "" # the location where the libraries will be installed
        #if no compile file set up and assume external is next to setup.py
        if not args.compfile:
            self.extDirLoc = "external"
            #self.extDirLoc = os.path.abspath(os.path.join(os.path.dirname(__file__), "external"))
        else:
            self.extDirLoc = os.path.abspath(self.parseForExtPath(args.compfile[0]))
        self.dirMaster_ = LibDirMaster(self.extDirLoc)
        self.args = args # command line arguments parsed by argument parser
        self.setUps = {} # all available set ups
        self.setUpsNeeded = [] # the setups that need to be done
        self.foundSetUpsNeeded = [] #the setups given by either parsing the comp file or command line, to be processed/check to be put into self.setUpsNeeded
        self.installed = [] # the setups that able to install
        self.failedInstall = [] # the setups that failed
        self.CC = "" # the c compilier being used
        self.CXX = "" # the c++ compilier being used
        self.noInternet_ = False
        if args.noInternet:
            self.noInternet_ = True
        self.__initSetUpFuncs()
        self.__processArgsForCompilers()
        self.__processArgsForSetupsNeeded()
        #add packages but with only the setups needed found
        packNames = [foundSetup.name for foundSetup in self.foundSetUpsNeeded]
        self.setupPackages(packNames)
        #then add setups needed found to be parsed/checked by packages
        for setupFound in self.foundSetUpsNeeded:
            self.packages_.addPackage(self.setUpsNeeded, setupFound)



    def setupPackages(self, packNames=[]):
        #if we have internet and the cache is more than a day old, clear it
        if Utils.connectedInternet:
            cacheDate = datetime.datetime.fromtimestamp(os.path.getmtime(self.dirMaster_.cache_dir))
            now = datetime.datetime.now()
            if 86400 < (now - cacheDate).total_seconds():
                self.clearCache()
        if self.args.clearCache:
            self.clearCache()
        self.packages_ = Packages(self.extDirLoc, self.args, packNames) # path object to hold the paths for install

    def getAllAvailablePackages(self):
        return list(self.setUps.keys())

    def setup(self):
        if self.args.forceUpdate:
            for setUpNeeded in self.setUpsNeeded:
                if not setUpNeeded.name in list(self.setUps.keys()):
                    print(CT.boldBlack( "Unrecognized option ") + CT.boldRed(setUpNeeded.name))
                else:
                    self.rmDirsForLib(setUpNeeded)

        for setUpNeeded in self.setUpsNeeded:
            if not setUpNeeded.name in list(self.setUps.keys()):
                print(CT.boldBlack( "Unrecognized option ") + CT.boldRed(setUpNeeded.name))
            else:
                if hasattr(setUpNeeded, "commit"):
                    self.__setup(setUpNeeded.name, setUpNeeded.version, setUpNeeded.commit)
                else:
                    self.__setup(setUpNeeded.name, setUpNeeded.version)

        for p in self.installed:
            if hasattr(p, "commit"):
                print(p.name + ":" + str(p.version)+ ":" + str(p.commit), CT.boldGreen("installed"))
            else:
                print(p.name + ":" + str(p.version), CT.boldGreen("installed"))

        for p in self.failedInstall:
            if hasattr(p, "commit"):
                print(p.name + ":" + str(p.version)+ ":" + str(p.commit), CT.boldRed("failed to install"))
            else:
                print(p.name + ":" + str(p.version), CT.boldRed("failed to install"))

    def __initSetUpFuncs(self):
        self.setUps = {"zi_lib": self.zi_lib,
                       "boost": self.boost,
                       "boost_filesystem": self.boost_filesystem,
                       "boost_math": self.boost_math,

                       "cppitertools": self.cppitertools,
                       "catch": self.catch,
                       "cppprogutils": self.cppprogutils,
                       "r": self.r,
                       "bamtools": self.bamtools,
                       "cppcms": self.cppcms,
                       "armadillo": self.armadillo,
                       "libpca": self.libpca,
                       "njhseq": self.njhseq,
                       "seekdeep": self.SeekDeep,
                       "njhcpp": self.njhcpp,
                       "seqserver": self.seqserver,
                       "njhrinside": self.njhRInside,
                       "jsoncpp": self.jsoncpp,
                       "pstreams": self.pstreams,
                       "dlib": self.dlib,
                       "libsvm": self.libsvm,
                       "mongoc": self.mongoc,
                       "mongocxx": self.mongocxx,
                       "twobit" : self.twobit,
                       "sharedmutex" : self.sharedMutex,
                       "mathgl": self.mathgl,
                       "magic": self.magic,
                       "zlib": self.zlib,
                       "zlib-ng": self.zlibng,
                       "openblas": self.openblas,
                       "flash": self.flash,
                       "pigz": self.pigz,
                       "bowtie2": self.bowtie2,
                       "muscle": self.muscle,
                       "adapterremoval": self.adapterremoval,
                       "lastz": self.lastz,
                       "samtools": self.samtools,
                       "bcftools": self.bcftools,
                       "hts": self.hts,
                       "restbed": self.restbed,
                       "unqlite": self.unqlite,
                       "eigen": self.eigen,
                       "glpk": self.glpk,
                       "cmake": self.cmake,
                       "curl": self.curl,
                       "bhtsne": self.bhtsne,
                       "lapack": self.lapack,
                       "atlas": self.atlas,
                       "mipwrangler": self.mipwrangler,
                       "elucidator": self.elucidator,
                       "pathweaver": self.pathweaver
                       }
        if self.args.private:
            self.setUps["elucidatorlab"] = self.elucidatorlab;
        '''
        "mlpack": self.mlpack,
        "liblinear": self.liblinear,
        '''
    def printAvailableSetUps(self):
        self.__initSetUpFuncs()
        installs = sorted(self.getAllAvailablePackages())
        self.setupPackages(installs)
        print("Available installs:")
        print("To Install use ./setup.py --libs lib1:ver,lib2:ver,lib3:ver")
        print("E.g. ./setup.py --libs bamtools:v2.4.0,boost:1_60_0")
        for installAvail in installs:
            print(installAvail)
            pack = self.__package(installAvail)
            sys.stdout.write("\t")
            sys.stdout.write(",".join([p.replace("__", "/") for p in pack.getVersions()]))
            sys.stdout.write("\n")

    def printGitRefs(self):
        self.__initSetUpFuncs()
        print("Git branches and tags:")
        for setUpNeeded in self.setUpsNeeded:
            print(setUpNeeded.name)
            pack = self.__package(setUpNeeded.name)
            refs = pack.getGitRefs(pack.versions_[pack.defaultVersion_].bPaths_.url)
            print("\t" + "Branches")
            for b in refs.branches:
                print("\t\t" + b)
            print("\t" + "Tags")
            for t in refs.tags:
                print("\t\t" + t)

    def __processArgsForSetupsNeeded(self):
        if self.args.libs:
            inLibs = self.args.libs.split(",")
            for lib in inLibs:
                if ":" not in lib.lower():
                    raise Exception("Need to give version for " + lib)
                else:
                    libSplit = lib.split(":")
                    if 3 == len(libSplit):
                        self.foundSetUpsNeeded.append(LibNameVerCommit(libSplit[0].lower(), libSplit[1], libSplit[2]));
                    else:
                        self.foundSetUpsNeeded.append(LibNameVer(libSplit[0].lower(), libSplit[1]));
                    #self.packages_.addPackage(self.setUpsNeeded,LibNameVer(libSplit[0].lower(), libSplit[1]))
        if self.args.compfile:
            self.parseSetUpNeeded(self.args.compfile[0])
        self.__initSetUpFuncs()
        #check to see if package is available
        for foundSetup in self.foundSetUpsNeeded:
            if foundSetup.name not in self.setUps:
                raise Exception("Error " + foundSetup.name + " not available, options are: " + ",".join(self.getAllAvailablePackages()))

    def __processArgsForCompilers(self):
        if self.args.compfile:
            self.parserForCompilers(self.args.compfile[0])
        # if no compfile need to determine compiler, will default to env CC and CXX
        else:
            self.CC = genHelper.determineCC(self.args)
            self.CXX = genHelper.determineCXX(self.args)
            self.args.CC = self.CC
            self.args.CXX = self.CXX
        if "clang" in self.CXX:
            self.args.clang = True
        else:
            self.args.clang = False

    def parseForExtPath(self, fn):
        args = self.parseCompFile(fn)
        if "EXT_PATH" in args:
            extPath = args["EXT_PATH"].strip()
            extPath = extPath.replace("$(realpath", "")
            extPath = extPath.replace(")", "")
            extPath = extPath.strip()
        else:
            print("did not find external folder location; assuming ./external")
            extPath = "./external"
        return extPath

    def parseSetUpNeeded(self, fn):
        args = self.parseCompFile(fn)
        for k,v in args.items():
            if k.startswith("USE_"):
                if '0' != v:
                    if "#" in v:
                        valSplit = v.split("#")
                        if valSplit[0] == '1':
                            if ":" in valSplit[1]:
                                valSplitFurther = valSplit[1].split(":")
                                self.foundSetUpsNeeded.append(LibNameVerCommit(k[4:].lower(), valSplitFurther[0], valSplitFurther[1]));
                            else:
                                self.foundSetUpsNeeded.append(LibNameVer(k[4:].lower(), valSplit[1]));
                            #self.packages_.addPackage(self.setUpsNeeded, LibNameVer(k[4:].lower(),valSplit[1]))
                    else:
                        raise Exception("Need to supply version in compfile with USE_PACKAGE#Version[:commit]")
            elif "PRIVATE" == k and "TRUE" == v:
                self.args.private = True;



    def parseCompFile(self, fn):
        ret = {}
        with open(fn) as f:
            for line in f:
                if '=' in line:
                    toks = line.split('=')
                    ret[toks[0].strip()] = toks[1].strip()
        return ret

    def parserForCompilers(self, fn):
        args = self.parseCompFile(fn)
        if 'CC' in args:
            self.CC = args['CC']
            self.args.CC = self.CC
        if 'CXX' in args:
            self.CXX = args['CXX']
            self.args.CXX = self.CXX

    def rmDirsForLibs(self,libs):
        for l in libs:
            self.rmDirsForLib(l)

    def rmDirsForLib(self,packVer):
        if packVer.name not in self.setUps:
            print(CT.boldBlack( "Unrecognized package: ") + CT.boldRed(packVer.name))
        else:
            pack = self.__package(packVer.name)
            if not pack.hasVersion(packVer.version):
                raise Exception("No version " + str(packVer.version) + " for " + str(packVer.name))
            p = pack.versions_[packVer.version].bPaths_
            if os.path.exists(p.build_dir):
                print("Removing " + CT.boldBlack(p.build_dir))
                Utils.rm_rf(p.build_dir)
            if os.path.exists(p.local_dir):
                print("Removing " + CT.boldBlack(p.local_dir))
                Utils.rm_rf(p.local_dir)


    def __package(self, name):
        return self.packages_.package(name)

    def __setup(self, name, version, commit = ""):
        version = version.replace("/", "__")
        pack = self.__package(name)
        if not pack.hasVersion(version):
            raise Exception("Package " + str(name) + " doesn't have version " + str(version))
        if "" != commit and "git" != pack.libType_ and "git-headeronly" != pack.libType_:
            raise Exception("Error for " + str(name) + ":" + str(version) + ":" + str(commit) + " set a commit but library type isn't git or git-headeronly")


        if "" != commit:
            pack.versions_[version].nameVer_ = LibNameVer(name, commit)
            commit_local_dir = os.path.join(self.dirMaster_.install_dir, name, commit, name)
            commit_build_dir = os.path.join(self.dirMaster_.ext_build, name, commit)
            commit_build_sub_dir = os.path.join(self.dirMaster_.ext_build, name, commit, name)
            commit_url = pack.versions_[version].bPaths_.url
            pack.versions_[version].bPaths_ = BuildPaths(commit_url, commit_build_dir, commit_build_sub_dir, commit_local_dir)
            pack.versions_[version].includePath_ = os.path.join(joinNameVer(pack.versions_[version].nameVer_), "include")
            pack.versions_[version].libPath_ = os.path.join(joinNameVer(pack.versions_[version].nameVer_), "lib")
            pack.versions_[commit] = pack.versions_[version]
        bPath = pack.versions_[version].bPaths_
        if os.path.exists(bPath.local_dir):
            if "" != commit:
                print(CT.boldGreen(name + ":" + commit), "found at " + CT.boldBlue(bPath.local_dir))
            else:
                print(CT.boldGreen(name + ":" + version), "found at " + CT.boldBlue(bPath.local_dir))
        else:
            if "" == commit:
                print(CT.boldGreen(name + ":" + version), CT.boldRed("NOT"), "found; building...")
                print("Not found @", bPath.local_dir)
                try:
                    self.setUps[name](version)
                    self.installed.append(LibNameVer(name, version))
                except Exception as inst:
                    print(inst)
                    print(CT.boldRed("failed to install ") + name + ":" + str(version))
                    self.failedInstall.append(LibNameVer(name, version))
            else:
                print(CT.boldGreen(name + ":" + commit), CT.boldRed("NOT"), "found; building...")
                print("Not found @", bPath.local_dir)
                try:
                    self.setUps[name](commit)
                    self.installed.append(LibNameVerCommit(name, version, commit))
                except Exception as inst:
                    print(inst)
                    print(CT.boldRed("failed to install ") + name + ":" + str(commit))
                    self.failedInstall.append(LibNameVerCommit(name, version, commit))


    def num_cores(self):
        retCores = Utils.num_cores()
        if self.args.numCores:
            if self.args.numCores < retCores:
                retCores = self.args.numCores
        else:
            if retCores > 24:
                retCores  = math.floor(retCores/2)
            if 1 != retCores:
                retCores -= 1
            if retCores < 1:
                retCores = 1
        return int(retCores)

    def __buildFromFile(self, packVer, cmd):
        bPath = packVer.bPaths_
        if self.noInternet_:
            newUrl = bPath.url.replace(".git","/archive/" + str(packVer.nameVer_.version) + ".tar.gz").replace("git@github.com:", "https://github.com/")
            bPath = BuildPaths(newUrl, bPath.build_dir, bPath.build_sub_dir, bPath.local_dir)
            base_file = os.path.basename(bPath.url)
            fnp = os.path.join(self.dirMaster_.ext_tars,packVer.nameVer_.name, base_file)
            if not os.path.exists(fnp):
                raise Exception("Could not find file: " + str(fnp))
        else:
            print("\t Getting file...")
            Utils.mkdir(os.path.join(self.dirMaster_.ext_tars, packVer.nameVer_.name))
            fnp = Utils.get_file_if_size_diff(bPath.url, os.path.join(self.dirMaster_.ext_tars, packVer.nameVer_.name))
        Utils.clear_dir(bPath.build_dir)
        Utils.untar(fnp, bPath.build_dir)
        ##probably not the best way to do this as there is no guarantee that there is a directory there
        ##untaredDir = os.listdir(bPath.build_dir)[0]
        untarContents = os.listdir(bPath.build_dir);
        for untarContent in untarContents:
            if os.path.isdir(os.path.join(bPath.build_dir,untarContent)):
                untaredDir = untarContent;
                break;

        os.rename(os.path.join(bPath.build_dir, untaredDir), bPath.build_sub_dir)
        try:
            Utils.run_in_dir(cmd, bPath.build_sub_dir)
        except:
            print("\t Failed to build, removing {d}".format(d = bPath.local_dir))
            Utils.rm_rf(bPath.local_dir)
            sys.exit(1)

    def __buildFromGitBranch(self, packVer, cmd):
        bPath = packVer.bPaths_
        if self.noInternet_:
            self.__buildFromFile(packVer, cmd)
        else:
            if os.path.exists(bPath.build_sub_dir):
                print("pulling from {url}".format(url=bPath.url))
                pCmd = "git checkout " + packVer.nameVer_.version.replace("__", "/") + " && git pull && if [ -f .gitmodules ]; then git submodule init && git submodule update; fi "
                try:
                    Utils.run_in_dir(pCmd, bPath.build_sub_dir)
                except:
                    print("failed to pull from {url} with {cmd}".format(url=bPath.url, cmd = pCmd))
                    sys.exit(1)
            else:
                cCmd = "git clone -b " + packVer.nameVer_.version.replace("__", "/") + " {url} {d} ".format(url=bPath.url, d=bPath.build_sub_dir)
                submoduleCmd = "if [ -f .gitmodules ]; then git submodule init && git submodule update; fi"
                try:
                    Utils.run(cCmd)
                    Utils.run_in_dir(submoduleCmd, bPath.build_sub_dir)
                except:
                    print("failed to clone from {url}".format(url=bPath.url))
                    sys.exit(1)
            try:
                Utils.run_in_dir(cmd, bPath.build_sub_dir)
            except:
                print(("Failed to build, removing {d}".format(d = bPath.local_dir)))
                Utils.rm_rf(bPath.local_dir)
                sys.exit(1)

    def __buildFromGitTag(self, packVer, cmd):
        bPath = packVer.bPaths_
        ##if no internet build from tar file, file needs to be in tarballs folder
        if self.noInternet_:
            self.__buildFromFile(packVer, cmd)
        else:
            if os.path.exists(bPath.build_sub_dir):
                print("pulling from {url}".format(url=bPath.url))
                pCmd = "git checkout master && git pull && git checkout " + packVer.nameVer_.version.replace("__", "/") + " && if [ -f .gitmodules ]; then git submodule init && git submodule update; fi"
                try:
                    Utils.run_in_dir(pCmd, bPath.build_sub_dir)
                except Exception as e:
                    print(e)
                    print("failed to pull from {url}".format(url=bPath.url))
                    sys.exit(1)
            else:
                cCmd = "git clone {url} {d}".format(url=bPath.url, d=bPath.build_sub_dir)
                tagCmd = "git checkout {tag} && if [ -f .gitmodules ]; then git submodule init && git submodule update; fi ".format(tag=packVer.nameVer_.version.replace("__", "/"))
                try:
                    Utils.run(cCmd)
                    Utils.run_in_dir(tagCmd, bPath.build_sub_dir)
                except Exception as e:
                    print(e)
                    print("failed to clone from {url}".format(url=bPath.url))
                    sys.exit(1)
            try:
                Utils.run_in_dir(cmd, bPath.build_sub_dir)
            except Exception as e:
                print(e)
                print("failed to build in {BUILD}, removing {LOCAL}".format(BUILD=bPath.build_sub_dir, LOCAL = bPath.local_dir))
                Utils.rm_rf(bPath.local_dir)
                sys.exit(1)

    def __gitBranch(self, packVer):
        bPath = packVer.bPaths_
        '''
            For header only libraries, will be put directly into local
        '''
        if self.noInternet_:
            newUrl = bPath.url.replace(".git","/archive/" + str(packVer.nameVer_.version) + ".tar.gz").replace("git@github.com:", "https://github.com/")
            base_file = os.path.basename(newUrl)
            fnp = os.path.join(self.dirMaster_.ext_tars,packVer.nameVer_.name, base_file)
            Utils.clear_dir(os.path.dirname(bPath.local_dir))
            Utils.untar(fnp, os.path.dirname(bPath.local_dir))
            ## might not be the best way to do this but works for now
            untaredDir = os.listdir(os.path.dirname(bPath.local_dir))[0]
            os.rename(os.path.join(os.path.dirname(bPath.local_dir), untaredDir), bPath.local_dir)
        else:
            cCmd = "git clone -b {branch} {url} {d}".format(branch = packVer.nameVer_.version.replace("__", "/"),url=bPath.url, d=bPath.local_dir)
            submoduleCmd = "if [ -f .gitmodules ]; then git submodule init && git submodule update; fi"
            try:
                Utils.run(cCmd)
                Utils.run_in_dir(submoduleCmd, bPath.build_sub_dir)
            except Exception as e:
                print(e)
                print("failed to clone branch {branch} from {url}".format(branch = packVer.nameVer_.version.replace("__", "/"), url=bPath.url))
                sys.exit(1)

    def __gitTag(self, packVer):
        bPath = packVer.bPaths_
        '''
            For header only libraries, will be put directly into local
        '''
        if self.noInternet_:
            newUrl = bPath.url.replace(".git","/archive/" + str(packVer.nameVer_.version) + ".tar.gz").replace("git@github.com:", "https://github.com/")
            base_file = os.path.basename(newUrl)
            fnp = os.path.join(self.dirMaster_.ext_tars,packVer.nameVer_.name, base_file)
            Utils.clear_dir(os.path.dirname(bPath.local_dir))
            Utils.untar(fnp, os.path.dirname(bPath.local_dir))
            ## might not be the best way to do this but works for now
            untaredDir = os.listdir(os.path.dirname(bPath.local_dir))[0]
            os.rename(os.path.join(os.path.dirname(bPath.local_dir), untaredDir), bPath.local_dir)
        else:
            cmd = "git clone {url} {d}".format(url=bPath.url, d=Utils.shellquote(bPath.local_dir))
            tagCmd = "git checkout {tag} && if [ -f .gitmodules ]; then git submodule init && git submodule update; fi ".format(tag=packVer.nameVer_.version)
            try:
                Utils.run(cmd)
                Utils.run_in_dir(tagCmd, bPath.local_dir)
            except:
                print("failed to clone from {url}".format(url=bPath.url))
                sys.exit(1)

    def __defaultBuild(self, package, version, fromGitTag = True):
        pack = self.__package(package)
        if not pack.hasVersion(version):
            raise Exception("No set up for version " + str(version) + " for " + str(package))
        packVer = pack.versions_[version]
        bPaths = packVer.bPaths_
        cmd = pack.defaultBuildCmd_
        if packVer.cmd_ and "" != packVer.cmd_:
            cmd = packVer.cmd_
        cmd = cmd.format(external = Utils.shellquote(self.dirMaster_.base_dir), build_sub_dir = Utils.shellquote(bPaths.build_sub_dir), local_dir=Utils.shellquote(bPaths.local_dir), num_cores=self.num_cores(), CC=self.CC, CXX=self.CXX)
        Utils.mkdir(os.path.dirname(bPaths.local_dir))
        if "" != cmd and self.args.verbose:
            print(cmd)
        if "git" == pack.libType_:
            Utils.mkdir(bPaths.build_dir)
            if fromGitTag:
                self.__buildFromGitTag(packVer, cmd)
            else:
                self.__buildFromGitBranch(packVer, cmd)
        elif "git-headeronly" == pack.libType_:
            if fromGitTag:
                self.__gitTag(packVer)
            else:
                self.__gitBranch(packVer)
        elif "file" == pack.libType_:
            Utils.mkdir(bPaths.build_dir)
            self.__buildFromFile(packVer, cmd)
        elif "file-executable" == pack.libType_:
            Utils.mkdir(bPaths.build_dir)
            self.__buildFromFileExecutable(packVer, cmd)
        else:
            raise Exception("Unrecognized lib type " + str(pack.libType_))
        if Utils.isMac():
            libPath = os.path.join(bPaths.local_dir, "lib")
            if(os.path.exists(libPath)):
                Utils.fixDyLibOnMac(libPath)
        Utils.ensureLibDirectoryPresent(bPaths.local_dir)

    def __defaultNJHBuild(self, package, version):
        if "develop" == version or "release" in version or "master" == version:
            self.__defaultBuild(package, version, False)
        else:
            self.__defaultBuild(package, version, True)

    def linkInBin(self, package, version, overwrite = False):
        self.packages_.checkForPackVer(LibNameVer(package, version))
        masterBinDir = os.path.join(os.path.dirname(self.extDirLoc), "bin" )
        Utils.mkdir(masterBinDir)
        masterBinDir = os.path.abspath(masterBinDir)
        pack = self.packages_.package(package)
        installDir = pack.getLocalDir(version)
        if os.path.exists(os.path.join(installDir, "bin")):
            binFiles = os.listdir(os.path.join(installDir, "bin"))
            for bFile in binFiles:
                bFileFull = os.path.join(installDir, "bin", bFile)
                if os.path.isfile(bFileFull) and os.access(bFileFull, os.X_OK):
                    if os.path.exists(os.path.join(masterBinDir, bFile)):
                        if overwrite:
                            os.remove(os.path.join(masterBinDir, bFile))
                        else:
                            raise Exception("File: " + os.path.join(masterBinDir, bFile) + " already exists, use --overWrite to overWrite")
                    print("Linking " + CT.boldGreen(bFileFull) + " to " + CT.boldBlue(os.path.join(masterBinDir, bFile)))
                    os.symlink(bFileFull, os.path.join(masterBinDir, bFile))


    def linkInBinWithVersionName(self, package, version, overwrite = False):
        self.packages_.checkForPackVer(LibNameVer(package, version))
        masterBinDir = os.path.join(os.path.dirname(self.extDirLoc), "bin" )
        Utils.mkdir(masterBinDir)
        masterBinDir = os.path.abspath(masterBinDir)
        pack = self.packages_.package(package)
        installDir = pack.getLocalDir(version)
        if os.path.exists(os.path.join(installDir, "bin")):
            binFiles = os.listdir(os.path.join(installDir, "bin"))
            for bFile in binFiles:
                bFileFull = os.path.join(installDir, "bin", bFile)
                bFileOut = os.path.join(masterBinDir, bFile + "-" + version)
                if os.path.isfile(bFileFull) and os.access(bFileFull, os.X_OK):
                    if os.path.exists(bFileOut):
                        if overwrite:
                            os.remove(bFileOut)
                        else:
                            raise Exception("File: " + bFileOut + " already exists, use --overWrite to overWrite")
                    print("Linking " + CT.boldGreen(bFileFull) + " to " + CT.boldBlue(bFileOut))
                    os.symlink(bFileFull, bFileOut)


    def updateNJHProjects(self, njhProjects):
        inLibs = njhProjects.split(",")
        for lib in inLibs:
            if ":" not in lib.lower():
                raise Exception("Need to give version for " + lib)
            else:
                libSplit = lib.split(":")
                #self.packages_.addPackage(self.setUpsNeeded,LibNameVer(libSplit[0].lower(),libSplit[1]))
                self.foundSetUpsNeeded.append(LibNameVer(libSplit[0].lower(),libSplit[1]))
        packNames = [foundSetup.name for foundSetup in self.foundSetUpsNeeded]
        self.setupPackages(packNames)
        for setupFound in self.foundSetUpsNeeded:
            self.packages_.addPackage(self.setUpsNeeded, setupFound)

        for setUpNeeded in self.setUpsNeeded:
            pack = self.__package(setUpNeeded.name)
            bPaths = pack.versions_[setUpNeeded.version].bPaths_
            if os.path.exists(bPaths.local_dir):
                print("Removing " + CT.boldBlack(bPaths.local_dir))
                Utils.rm_rf(bPaths.local_dir)
        for setUpNeeded in self.setUpsNeeded:
            pack = self.__package(setUpNeeded.name)
            bPath = pack.versions_[setUpNeeded.version].bPaths_
            if os.path.exists(os.path.join(bPath.build_dir,setUpNeeded.name, "makefile-common.mk")):
                os.remove(os.path.join(bPath.build_dir,setUpNeeded.name, "makefile-common.mk"))
            self.__setup(setUpNeeded.name, setUpNeeded.version)
        for p in self.installed:
            print(p.name + ":" + str(p.version), CT.boldGreen("installed"))

        for p in self.failedInstall:
            print(p.name + ":" + str(p.version), CT.boldRed("failed to install"))


    def installRPackageSource(self,version, sourceFile):
        rPack = self.__package("r")
        if not rPack.hasVersion(version):
            raise Exception("No set up for version " + str(version) + " for " + str("R"))
        bPath = rPack.versions_[version].bPaths_
        for pack in sourceFile.split(","):
            rHomeLoc = "bin/R RHOME"
            #if Utils.isMac():
            #    rHomeLoc = "R.framework/Resources/bin/R RHOME"
            cmd = """echo '.libPaths(.libPaths()[length(.libPaths()  )] ); install.packages(\"{SOURCEFILE}\", repos = NULL, type="source", Ncpus = {num_cores}, lib =.libPaths()[length(.libPaths()  )])' | $({local_dir}/{RHOMELOC})/bin/R --slave --vanilla
                """.format(local_dir=Utils.shellquote(bPath.local_dir).replace(' ', '\\ '),SOURCEFILE = pack, RHOMELOC =rHomeLoc, num_cores=self.num_cores())
            print(CT.boldBlack(cmd))
            cmd = " ".join(cmd.split())
            Utils.run(cmd)

    def installRPackageName(self,version, packageName):
        rPack = self.__package("r")
        if not rPack.hasVersion(version):
            raise Exception("No set up for version " + str(version) + " for " + str("R"))
        bPath = rPack.versions_[version].bPaths_
        for pack in packageName.split(","):
            rHomeLoc = "bin/R RHOME"
            #if Utils.isMac():
            #    rHomeLoc = "R.framework/Resources/bin/R RHOME"
            cmd = """echo '.libPaths(.libPaths()[length(.libPaths()  )] ); install.packages(\"{PACKAGENAME}\", repos=\"http://cran.us.r-project.org\", Ncpus = {num_cores}, lib =.libPaths()[length(.libPaths()  )])'  | $({local_dir}/{RHOMELOC})/bin/R --slave --vanilla
                """.format(local_dir=Utils.shellquote(bPath.local_dir).replace(' ', '\\ '),PACKAGENAME = pack, RHOMELOC =rHomeLoc,num_cores=self.num_cores() )
            print(CT.boldBlack(cmd))
            cmd = " ".join(cmd.split())
            Utils.run(cmd)

    def boost(self, version):
        self.__defaultBuild("boost", version)

    def boost_filesystem(self, version):
        self.__defaultBuild("boost_filesystem", version)

    def boost_math(self, version):
        self.__defaultBuild("boost_math", version)

    def r(self, version):
        package = "r"
        verSplit = version.split(".")
        verNameStr = verSplit[0] + verSplit[1] + verSplit[2]
        verNameInt = int(verNameStr)
        #print verSplit
        #print verNameStr
        #print verNameInt
        if verNameInt >= 330 and Utils.isMac( ):
            pack = self.__package(package)
            rHomeLoc = "bin/R RHOME"
            #&& echo 'install.packages(c(\"gridExtra\", \"ape\", \"ggplot2\", \"seqinr\",\"Rcpp\", \"RInside\",\"devtools\"),
            #r.dylib needs rblas
            #rlapack needs r and rblas
            #rinside needs r
            #install_name_tool -change $(otool -L $(realpath .)/lib/R/library/RInside/lib/libRInside.dylib | egrep -o "\s.*libR.dylib") $(realpath .)/lib/R/lib/libR.dylib $(realpath .)/lib/R/library/RInside/lib/libRInside.dylib
            buildCmd = r"""./configure --prefix={local_dir} --enable-R-shlib --with-x=no CC={CC} CXX={CXX} OBJC={CC}
                    && make -j {num_cores}
                    && make install
                    && install_name_tool -id {local_dir}/lib/R/lib/libR.dylib {local_dir}/lib/R/lib/libR.dylib
                    && install_name_tool -id {local_dir}/lib/R/lib/libRlapack.dylib {local_dir}/lib/R/lib/libRlapack.dylib
                    && install_name_tool -id {local_dir}/lib/R/lib/libRblas.dylib {local_dir}/lib/R/lib/libRblas.dylib
                    && install_name_tool -change $(otool -L {local_dir}/lib/R/lib/libR.dylib | egrep -o "\s.*libRblas.dylib") {local_dir}/lib/R/lib/libRblas.dylib {local_dir}/lib/R/lib/libR.dylib
                    && install_name_tool -change $(otool -L {local_dir}/lib/R/lib/libRlapack.dylib | egrep -o "\s.*libRblas.dylib") {local_dir}/lib/R/lib/libRblas.dylib {local_dir}/lib/R/lib/libRlapack.dylib
                    && install_name_tool -change $(otool -L {local_dir}/lib/R/lib/libRlapack.dylib | egrep -o "\s.*libR.dylib") {local_dir}/lib/R/lib/libR.dylib {local_dir}/lib/R/lib/libRlapack.dylib
                    && echo 'install.packages(c(\"gridExtra\", \"ape\", \"ggplot2\", \"seqinr\",\"Rcpp\", \"RInside\"),
                    repos=\"http://cran.us.r-project.org\", Ncpus = {num_cores}, lib =.libPaths()[length(.libPaths()  )])' | $({local_dir}/""" + rHomeLoc + r""")/bin/R --slave --vanilla
                    """
            buildCmd = " ".join(buildCmd.split())
            pack.defaultBuildCmd_ = buildCmd
        self.__defaultBuild("r", version)

    def bamtools(self, version):
        self.__defaultNJHBuild("bamtools", version)

    def njhcpp(self, version):
        self.__defaultNJHBuild("njhcpp", version)

    def njhseq(self, version):
        self.__defaultNJHBuild("njhseq", version)

    def twobit(self, version):
        self.__defaultNJHBuild("twobit", version)

    def sharedMutex(self, version):
        self.__defaultNJHBuild("sharedmutex", version)

    def SeekDeep(self, version):
        self.__defaultNJHBuild("seekdeep", version)

    def seqserver(self, version):
        self.__defaultNJHBuild("seqserver", version)

    def mipwrangler(self, version):
        self.__defaultNJHBuild("mipwrangler", version)

    def pathweaver(self, version):
        self.__defaultNJHBuild("pathweaver", version)

    def elucidator(self, version):
        self.__defaultNJHBuild("elucidator", version)

    def elucidatorlab(self, version):
        self.__defaultNJHBuild("elucidatorlab", version)

    def bhtsne(self, version):
        self.__defaultNJHBuild("bhtsne", version)

    def MIPWrangler(self, version):
        self.__defaultNJHBuild("mipwrangler", version)

    def njhRInside(self, version):
        self.__defaultNJHBuild("njhrinside", version)

    def cppprogutils(self, version):
        self.__defaultNJHBuild("cppprogutils", version)

    def jsoncpp(self, version):
        self.__defaultBuild("jsoncpp", version)

    def lapack(self, version):
        self.__defaultBuild("lapack", version)

    def atlas(self, version):
        self.__defaultBuild("atlas", version)


    def mongoc(self, version):
        self.__defaultBuild("mongoc", version)

    def mongocxx(self, version):
        package = "mongocxx"
        pack = self.__package(package)
        if not pack.hasVersion(version):
            raise Exception("No set up for version " + str(version) + " for " + str(package))
        packVer = pack.versions_[version]
        bPaths = packVer.bPaths_
        pack.defaultBuildCmd_ = pack.defaultBuildCmd_.format(mongoc_ver = packVer.depends_[0].version,external = self.dirMaster_.base_dir, build_sub_dir = Utils.shellquote(bPaths.build_sub_dir), local_dir=Utils.shellquote(bPaths.local_dir), num_cores=self.num_cores(), CC=self.CC, CXX=self.CXX)
        self.__defaultBuild("mongocxx", version)

    def cppcms(self, version):
        self.__defaultBuild("cppcms", version)

    def armadillo(self, version):
        self.__defaultBuild("armadillo", version)

    def libpca(self, version):
        self.__defaultBuild("libpca", version)

    def zi_lib(self, version):
        self.__defaultBuild("zi_lib", version)

    def pstreams(self, version):
        self.__defaultBuild("pstreams", version)

    def cppitertools(self, version):
        self.__defaultBuild("cppitertools", version)

    def dlib(self, version):
        self.__defaultBuild("dlib", version)

    def libsvm(self, version):
        self.__defaultBuild("libsvm", version)

    def catch(self, version):
        self.__defaultBuild("catch", version)

    def mathgl(self, version):
        self.__defaultBuild("mathgl", version)

    def magic(self, version):
        self.__defaultBuild("magic", version)

    def zlib(self, version):
        self.__defaultBuild("zlib", version)

    def zlibng(self, version):
        self.__defaultBuild("zlib-ng", version)

    def openblas(self, version):
        self.__defaultBuild("openblas", version)

    def flash(self, version):
        self.__defaultBuild("flash", version)

    def pigz(self, version):
        self.__defaultBuild("pigz", version)

    def bowtie2(self, version):
        self.__defaultBuild("bowtie2", version)

    def muscle(self, version):
        self.__defaultBuild("muscle", version)

    def adapterremoval(self, version):
        self.__defaultBuild("adapterremoval", version)

    def lastz(self, version):
        self.__defaultBuild("lastz", version)

    def samtools(self, version):
        self.__defaultBuild("samtools", version)

    def bcftools(self, version):
        self.__defaultBuild("bcftools", version)

    def hts(self, version):
        self.__defaultBuild("hts", version)

    def restbed(self, version):
        self.__defaultBuild("restbed", version)

    def unqlite(self, version):
        self.__defaultBuild("unqlite", version)

    def eigen(self, version):
        self.__defaultBuild("eigen", version)

    def glpk(self, version):
        self.__defaultBuild("glpk", version)

    def cmake(self, version):
        self.__defaultBuild("cmake", version)

    def curl(self, version):
        self.__defaultBuild("curl", version)
    #


    def downloadFiles(self):
        for setUpNeeded in self.setUpsNeeded:
            topTempDir = os.path.join(self.dirMaster_.base_dir, "temp")
            self.packages_.checkForPackVer(setUpNeeded)
            pack = self.__package(setUpNeeded.name)
            packVer = pack.versions_[setUpNeeded.version]
            downloadDir = os.path.join(self.dirMaster_.ext_tars, pack.name_)
            Utils.mkdir(downloadDir)
            if pack.njhProject_:
                downloadCmd = "./configure.py -CC {CC} -CXX {CXX} -externalLibDir {external} && ./setup.py --compfile compfile.mk --justDownload".format(external = Utils.shellquote(self.dirMaster_.base_dir), num_cores=self.num_cores(), CC=self.CC, CXX=self.CXX)
                Utils.mkdir(topTempDir)
                packVer = pack.versions_[setUpNeeded.version]
                tempDir = os.path.join(topTempDir, pack.name_)
                cloneCmd = "git clone {url} {d}".format(url=packVer.bPaths_.url, d = tempDir)
                tagCmd = "git checkout {tag}".format(tag=packVer.nameVer_.version.replace("__", "/"))
                Utils.run(cloneCmd)
                Utils.run_in_dir(tagCmd, tempDir)
                Utils.run_in_dir(downloadCmd, tempDir)
                if "develop" == setUpNeeded.version or "master" == setUpNeeded.version or "release" in setUpNeeded.version:
                    archiveCmd = "git archive --prefix={name}/ -o {downloadDir}/{version}.tar.gz HEAD".format(name = pack.name_, downloadDir = downloadDir, version = setUpNeeded.version)
                    Utils.run_in_dir(archiveCmd, tempDir)
                shutil.rmtree(tempDir)
            if pack.njhProject_ and ("develop" == setUpNeeded.version or "master" == setUpNeeded.version or "release" in setUpNeeded.version):
                pass
            else:
                url = packVer.getDownloadUrl()
                dest = os.path.join(self.dirMaster_.ext_tars, packVer.nameVer_.name)
                print(("Downloading " + CT.boldGreen(url) + " to " + CT.boldBlue(dest)))
                if pack.libType_.startswith("git"):
                    fnp = Utils.get_file(url, dest)
                else:
                    fnp = Utils.get_file_if_size_diff(url, dest)

        if os.path.exists(os.path.join(self.dirMaster_.base_dir, "temp")) and os.listdir(os.path.join(self.dirMaster_.base_dir, "temp")) == []:
            shutil.rmtree(os.path.join(self.dirMaster_.base_dir, "temp"))
        print ("Now run \"./setup.py --compfile compfile.mk --outMakefile makefile-common.mk --noInternet\" to build libraries")

    def externalChecks(self):
        ccWhich = Utils.which(self.CC)
        cxxWhich = Utils.which(self.CXX)
        cmakeWhich = Utils.which("cmake")
        gitWhich = Utils.which("git")
        failure = False;
        if not ccWhich or not cxxWhich or not cmakeWhich or not gitWhich:
            if not ccWhich:
                print(CT.boldRed("Could not find c compiler " + CT.purple + self.CC))
                if self.args.compfile:
                    print("Change CC in " + self.args.compfile[0])
                else:
                    print("Can supply another c compiler by using -CC [option] or by defining bash environmental CC ")
                print("")
                failure = True
            if not cxxWhich:
                print(CT.boldRed("Could not find c++ compiler " + CT.purple + self.CXX))
                if self.args.compfile:
                    print("Change CXX in " + self.args.compfile[0])
                else:
                    print("Can supply another c++ compiler by using -CXX [option] or by defining bash environmental CXX ")
                print("")
                failure = True
            if not cmakeWhich and "cmake" not in self.packages_.packages_:
                failure = True
                print(CT.boldRed("Could not find " + CT.purple + "cmake"))
                if Utils.isMac():
                    print("If you have brew, you can install via, brew update && brew install cmake, otherwise you can follow instructions from http://www.cmake.org/install/")

                else:
                    print("On ubuntu to install latest cmake do the following")
                    print("sudo add-apt-repository ppa:george-edison55/cmake-3.x")
                    print("sudo apt-get update")
                    print("sudo apt-get install cmake")
                    print("or if you have linuxbrew, brew install cmake")
            if not gitWhich:
                failure = True
                print ("Can't find commandline tool git")
            if failure:
                raise Exception()



    def clearCache(self):
        Utils.rm_rf(self.dirMaster_.cache_dir)
        Utils.mkdir(self.dirMaster_.cache_dir)

    def clean(self):
        Utils.rm_rf(self.dirMaster_.ext_build)
        Utils.rm_rf(self.dirMaster_.ext_tars)



class SetupRunner:
    @staticmethod
    def ubuntu(self):
        pkgs = """libbz2-dev python2.7-dev cmake libpcre3-dev zlib1g-dev libgcrypt11-dev libicu-dev
    python doxygen doxygen-gui auctex xindy graphviz libcurl4-openssl-dev""".split()
        return pkgs

    @staticmethod
    def parse_args():
        parser = argparse.ArgumentParser()
        parser.add_argument('--compfile', type=str, nargs=1)
        parser.add_argument('--libs', type=str, help="The libraries to install")
        parser.add_argument('--printLibs', action = "store_true", help="Print Available Libs")
        parser.add_argument('--printGitRefs', action = "store_true", help="Print Git branhes and tags for git projects")
        parser.add_argument('--forceUpdate', action = "store_true", help="Remove already installed libs and re-install")
        parser.add_argument('--updateNJHProjects', type = str, help="Remove already installed libs and re-install")
        parser.add_argument('--CC', type=str, nargs=1)
        parser.add_argument('--CXX', type=str, nargs=1)
        parser.add_argument('--instRPackageName',type=str, nargs=1)
        parser.add_argument('--instRPackageSource',type=str, nargs=1)
        parser.add_argument('--addBashCompletion', dest = 'addBashCompletion', action = 'store_true')
        parser.add_argument('--numCores', type=int)
        parser.add_argument('--outMakefile', type=str)
        parser.add_argument('--overWrite', action = 'store_true')
        parser.add_argument('--append', action = 'store_true')
        parser.add_argument('--noInternet', action = 'store_true')
        parser.add_argument('--justDownload', action = 'store_true')
        parser.add_argument('--verbose', action = 'store_true')
        parser.add_argument('--symlinkBin', action = 'store_true', help = "Symlink in executables into a directory bin next to external")
        parser.add_argument('--symlinkBinVersion', action = 'store_true', help = "Symlink in executables into a directory bin next to external with version name")

        parser.add_argument('--clearCache', action = 'store_true')
        parser.add_argument('--clean', action = 'store_true',  help = "Remove intermediate build files to save space")
        parser.add_argument('--private', action = 'store_true',  help = "Add the private repos elucidatorlab if you have the rights to access")

        return parser.parse_args()

    @staticmethod
    def runSetup():
        args = SetupRunner.parse_args()
        s = Setup(args)
        if args.printLibs:
            s.printAvailableSetUps()
            return 0
        if args.addBashCompletion:
            if(os.path.isdir("./bashCompletes")):
                cmd = "echo >> ~/.bash_completion && cat bashCompletes/* >> ~/.bash_completion"
                Utils.run(cmd)
            if(os.path.isdir("./bash_completion.d")):
                cmd = "echo >> ~/.bash_completion && cat bash_completion.d/* >> ~/.bash_completion"
                Utils.run(cmd)
            if(os.path.isdir("./etc/bash_completion.d")):
                cmd = "echo >> ~/.bash_completion && cat ./etc/bash_completion.d/* >> ~/.bash_completion"
                Utils.run(cmd)
            return 0
        s.externalChecks()
        if(args.instRPackageName):
            s.setupPackages("r")
            s.installRPackageName(s.packages_.packages_["r"].defaultVersion_, args.instRPackageName[0])
            return 0
        if(args.instRPackageSource):
            s.setupPackages("r")
            s.installRPackageSource( s.packages_.packages_["r"].defaultVersion_, args.instRPackageSource[0])
            return 0
        if args.updateNJHProjects:
            s.updateNJHProjects(args.updateNJHProjects)
            return 0

        if args.clean:
            s.clean()
            return 0
        if len(s.setUpsNeeded) == 0 and not args.compfile:
            print(("To see available setup use " + str(__file__).replace(".pyc", ".py") + " --printLibs"))
            #s.printAvailableSetUps()
            return 0
        elif args.printGitRefs:
            s.printGitRefs()
            return 0
        else:
            if args.justDownload:
                s.downloadFiles()
            else:
                s.setup()
                if args.outMakefile:
                    packVers = []
                    for setUpNeeded in s.setUpsNeeded:
                        s.packages_.addPackage(packVers,setUpNeeded)
                    s.packages_.writeMakefile(packVers, args.outMakefile, args.overWrite, args.append)
                if args.symlinkBin:
                    for setUpNeeded in s.setUpsNeeded:
                        s.linkInBin(setUpNeeded.name, setUpNeeded.version, args.overWrite)
                if args.symlinkBinVersion:
                    for setUpNeeded in s.setUpsNeeded:
                        s.linkInBinWithVersionName(setUpNeeded.name, setUpNeeded.version, args.overWrite)
                return 0

if __name__ == '__main__':
    #setups = [LibNameVer("njhcpp", "develop"), LibNameVerCommit("njhseq", "develop", "9d63c89")]
    #for s in setups:
    #    print(hasattr(s, "commit"))
    SetupRunner.runSetup()
