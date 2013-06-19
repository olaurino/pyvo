#!/usr/bin/env python
"""
Tests for vaopy.dal.query
"""
import os, sys, shutil, re, imp, glob
import unittest, pdb
from urllib2 import URLError, HTTPError

import vaopy.dal.query as dalq
import vaopy.dal.ssa as ssa
import vaopy.dal.dbapi2 as daldbapi
# from astropy.io.vo import parse as votableparse
from astropy.io.votable.tree import VOTableFile
from vaopy.dal.query import _votableparse as votableparse

testdir = os.path.dirname(sys.argv[0])
if not testdir:  testdir = "tests"
ssaresultfile = "jhu-ssa.xml"
errresultfile = "error-ssa.xml"
testserverport = 8081

try:
    t = "aTestSIAServer"
    mod = imp.find_module(t, [testdir])
    testserver = imp.load_module(t, mod[0], mod[1], mod[2])
    testserver.testdir = testdir
except ImportError, e:
    print >> sys.stderr, "Can't find test server: aTestSIAServer.py:", str(e)

class SSAServiceTest(unittest.TestCase):

    baseurl = "http://localhost/ssa"

    def testCtor(self):
        self.res = {"title": "Archive", "shortName": "arch"}
        self.srv = ssa.SSAService(self.baseurl, resmeta=self.res)

    def testProps(self):
        self.testCtor()
        self.assertEquals(self.srv.baseurl, self.baseurl)
        self.assertEquals(self.srv.protocol, "ssa")
        self.assertEquals(self.srv.version, "1.0")
        try:
            self.srv.baseurl = "goober"
            self.fail("baseurl not read-only")
        except AttributeError:
            pass

        self.assertEquals(self.srv.description["title"], "Archive")
        self.assertEquals(self.srv.description["shortName"], "arch")
        self.srv.description["title"] = "Sir"
        self.assertEquals(self.res["title"], "Archive")

    def testCreateQuery(self):
        self.testCtor()
        q = self.srv.create_query()
        self.assert_(isinstance(q, ssa.SSAQuery))
        self.assertEquals(q.baseurl, self.baseurl)
        self.assertEquals(len(q._param.keys()), 1)

    def testCreateQueryWithArgs(self):
        self.testCtor()
        q = self.srv.create_query(pos=(0,0), size=1.0, format="all")
        self.assert_(isinstance(q, ssa.SSAQuery))
        self.assertEquals(q.baseurl, self.baseurl)
        self.assertEquals(len(q._param.keys()), 4)

        self.assertEquals(q.pos, (0,0))
        self.assertEquals(q.size, 1.0)
        self.assertEquals(q.format, "all")

        qurl = q.getqueryurl()
        self.assert_("REQUEST=queryData" in qurl)
        self.assert_("POS=0,0" in qurl)
        self.assert_("SIZE=1.0" in qurl)
        self.assert_("FORMAT=all" in qurl)

    def testCreateQueryWithKws(self):
        self.testCtor()
        q = self.srv.create_query(APERTURE=0.00028)
        self.assertAlmostEquals(0.00028, q.getparam("APERTURE"))

        q.pos = (0,0)
        q.size = 1.0
        self.assertEquals(q.pos, (0,0))
        self.assertEquals(q.size, 1.0)
        self.assertEquals(len(q._param.keys()), 4)
        self.assertAlmostEquals(q.getparam('APERTURE'), 0.00028)

        qurl = q.getqueryurl()
        self.assert_("REQUEST=queryData" in qurl)
        self.assert_("POS=0,0" in qurl)
        self.assert_("SIZE=1.0" in qurl)
        self.assertTrue("APERTURE=0.00028" in qurl, 
                        "unexpected APERTURE format: "+qurl)

        q = self.srv.create_query(pos=(0,0), size=1.0, format="all", 
                                  APERTURE=0.00028)
        self.assert_(isinstance(q, ssa.SSAQuery))
        self.assertEquals(q.baseurl, self.baseurl)
        self.assertEquals(len(q._param.keys()), 5)

        self.assertEquals(q.pos, (0,0))
        self.assertEquals(q.size, 1.0)
        self.assertEquals(q.format, "all")
        self.assertAlmostEquals(q.getparam('APERTURE'), 0.00028)

        qurl = q.getqueryurl()
        self.assert_("REQUEST=queryData" in qurl)
        self.assert_("POS=0,0" in qurl)
        self.assert_("SIZE=1.0" in qurl)
        self.assert_("FORMAT=all" in qurl)
        self.assertTrue("APERTURE=0.00028" in qurl, 
                        "unexpected APERTURE format: "+qurl)

        


class SSAQueryTest(unittest.TestCase):

    baseurl = "http://localhost/ssa"

    def testCtor(self):
        self.q = ssa.SSAQuery(self.baseurl)
        self.assertEquals(self.q.baseurl, self.baseurl)
        self.assertEquals(self.q.protocol, "ssa")
        self.assertEquals(self.q.version, "1.0")

    def testPos(self):
        self.testCtor()
        self.assert_(self.q.pos is None)
        self.assert_(self.q.ra is None)
        self.assert_(self.q.dec is None)

        self.q.ra = 120.445
        self.assertEquals(self.q.ra, 120.445)
        self.assertEquals(self.q.dec, 0)
        self.assertEquals(self.q.pos, (120.445, 0))

        del self.q.pos
        self.assert_(self.q.pos is None)
        self.assert_(self.q.ra is None)
        self.assert_(self.q.dec is None)

        self.q.dec = 40.1434
        self.assertEquals(self.q.dec, 40.1434)
        self.assertEquals(self.q.ra, 0)
        self.assertEquals(self.q.pos, (0, 40.1434))

        self.q.pos = (180.2, -30.1)
        self.assertEquals(self.q.ra, 180.2)
        self.assertEquals(self.q.dec, -30.1)
        self.assertEquals(self.q.pos, (180.2, -30.1))

        self.q.pos = [170.2, -20.1]
        self.assertEquals(self.q.ra, 170.2)
        self.assertEquals(self.q.dec, -20.1)
        self.assertEquals(self.q.pos, (170.2, -20.1))

        self.q.ra = -45
        self.assertEquals(self.q.ra, 315)
        self.q.ra = 400
        self.assertEquals(self.q.ra, 40)

    def testBadPos(self):
        self.testCtor()
        try:
            self.q.pos = 22.3; self.fail("pos took scalar value")
        except ValueError:  pass
        try:
            self.q.pos = range(4); self.fail("pos took bad-length array value")
        except ValueError:  pass
        try:
            self.q.pos = "a b".split(); self.fail("pos took string values")
        except ValueError:  pass
        try:
            self.q.ra = "a b"; self.fail("ra took string values")
        except ValueError:  pass
        try:
            self.q.dec = "a b"; self.fail("dec took string values")
        except ValueError:  pass
        try:
            self.q.dec = 100; self.fail("dec took out-of-range value")
        except ValueError, e:  pass
            
            
    def testSize(self):
        self.testCtor()
        self.assert_(self.q.size is None)

        self.q.size = 1.5
        self.assertEquals(self.q.size, 1.5)

        del self.q.size
        self.assert_(self.q.size is None)

        self.q.size = 0.5
        self.assertEquals(self.q.size, 0.5)

    def testBadSize(self):
        self.testCtor()
        try:  self.q.size = "a"; self.fail("size took non-numbers")
        except ValueError: pass

        try:  self.q.size = 200; self.fail("size took out-of-range dec")
        except ValueError: pass

        try:  self.q.size = 0; self.fail("size took out-of-range dec")
        except ValueError: pass

        try:  self.q.size = -5; self.fail("size took out-of-range dec")
        except ValueError: pass

    def testProps(self):
        self.testCtor()
        self.assert_(self.q.format is None)
        self.q.format = "all"
        self.assertEquals(self.q.format, "all")
        del self.q.format
        self.assert_(self.q.format is None)


    def testCreateURL(self):
        self.testCtor()
        self.q.ra = 102.5511
        self.q.dec = 24.312
        qurl = self.q.getqueryurl()
        self.assertEquals(qurl, self.baseurl+"?REQUEST=queryData&POS=102.5511,24.312")

        self.q.size = 1.0
        qurl = self.q.getqueryurl()
        self.assert_("POS=102.5511,24.312" in qurl)
        self.assert_("SIZE=1.0" in qurl)


class SSAResultsTest(unittest.TestCase):

    def setUp(self):
        resultfile = os.path.join(testdir, ssaresultfile)
        self.tbl = votableparse(resultfile)

    def testCtor(self):
        self.r = ssa.SSAResults(self.tbl)
        self.assertEquals(self.r.protocol, "ssa")
        self.assertEquals(self.r.version, "1.0")
        self.assert_(isinstance(self.r._fldnames, list))
        self.assert_(self.r._tbl is not None)
        self.assertEquals(self.r.rowcount, 35)

    def testUTypeMap(self):
        self.testCtor()
        self.assertEquals(self.r._ssacols["ssa:DataID.Title"], "Title")
        self.assertEquals(self.r._ssacols["ssa:Target.Pos"], "TargetPos")
        self.assertEquals(self.r._ssacols["ssa:Access.Reference"], "AcRef")
        #        self.assert_(self.r._ssacols["VOX:Image_AccessRefTTL"] is None)

        self.assertEquals(self.r._recnames["title"], "Title")
        self.assertEquals(self.r._recnames["pos"], "TargetPos")
        self.assertEquals(self.r._recnames["acref"], "AcRef")
        self.assertEquals(self.r._recnames["dateobs"], "CreatorDate")

    def testGetRecord(self):
        self.testCtor()
        rec = self.r.getrecord(0)
        self.assert_(isinstance(rec, ssa.SSARecord))
        rec = self.r.getrecord(1)
        self.assert_(isinstance(rec, ssa.SSARecord))

class SSAResultsErrorTest(unittest.TestCase):

    def setUp(self):
        resultfile = os.path.join(testdir, errresultfile)
        self.tbl = votableparse(resultfile)

    def testError(self):
        try:
            res = ssa.SSAResults(self.tbl)
            self.fail("Failed to detect error response")
        except dalq.DalQueryError, ex:
            self.assertEquals(ex.label, "ERROR")
            self.assertEquals(ex.reason, "Forced Fail")

class SSARecordTest(unittest.TestCase):

    acref = "http://vaosa-vm1.aoc.nrao.edu/ivoa-dal/JhuSsapServlet?REQUEST=getData&FORMAT=votable&PubDID=ivo%3A%2F%2Fjhu%2Fsdss%2Fdr6%2Fspec%2F2.5%2380442261170552832"

    def setUp(self):
        resultfile = os.path.join(testdir, ssaresultfile)
        self.tbl = votableparse(resultfile)
        self.result = ssa.SSAResults(self.tbl)
        self.rec = self.result.getrecord(0)

    def testNameMap(self):
        self.assertEquals(self.rec._names["title"], "Title")
        self.assertEquals(self.rec._names["pos"], "TargetPos")
        self.assertEquals(self.rec._names["acref"], "AcRef")
        self.assertEquals(self.rec._names["dateobs"], "CreatorDate")

    def testAttr(self):
        self.assertEquals(self.rec.ra, 179.84916)
        self.assertEquals(self.rec.dec, 0.984768)
        self.assertEquals(self.rec.title, "SDSS J115923.80+005905.16 GALAXY")
        self.assertEquals(self.rec.dateobs, "2000-04-29 03:22:00Z")
        self.assertEquals(self.rec.instr, "SDSS 2.5-M SPEC2 v4_5")
        self.assertEquals(self.rec.acref, self.acref)
        self.assertEquals(self.rec.getdataurl(), self.acref)

class SSAExecuteTest(unittest.TestCase):

    def testExecute(self):
        q = ssa.SSAQuery("http://localhost:%d/ssa" % testserverport)
        q.pos = (0, 0)
        q.size = 1.0
        q.format = "all"
        results = q.execute()
        self.assert_(isinstance(results, ssa.SSAResults))
        self.assertEquals(results.rowcount, 35)

    def testSearch(self):
        srv = ssa.SSAService("http://localhost:%d/ssa" % testserverport)
        results = srv.search(pos=(0,0), size=1.0)
        self.assert_(isinstance(results, ssa.SSAResults))
        self.assertEquals(results.rowcount, 35)

        qurl = results.queryurl
        # print qurl
        self.assert_("REQUEST=queryData" in qurl)
        self.assert_("POS=0,0" in qurl)
        self.assert_("SIZE=1.0" in qurl)
        self.assert_("FORMAT=all" in qurl)


    def testSsa(self):
        results = ssa.search("http://localhost:%d/ssa" % testserverport,
                             pos=(0,0), size=1.0)
        self.assert_(isinstance(results, ssa.SSAResults))
        self.assertEquals(results.rowcount, 35)

    def testError(self):
        srv = ssa.SSAService("http://localhost:%d/err" % testserverport)
        self.assertRaises(dalq.DalQueryError, srv.search, (0.0,0.0), 1.0)
        

class DatasetNameTest(unittest.TestCase):

    base = "testspec"

    def setUp(self):
        resultfile = os.path.join(testdir, ssaresultfile)
        self.tbl = votableparse(resultfile)
        self.result = ssa.SSAResults(self.tbl)
        self.rec = self.result.getrecord(0)

        self.cleanfiles()

    def tearDown(self):
        self.cleanfiles()

    def cleanfiles(self):
        files = glob.glob(os.path.join(testdir, self.base+"*.*"))
        for f in files:
            os.remove(f)

    def testSuggest(self):
        self.assertEquals("SDSS_J115923.80+005905.16_GALAXY", 
                          self.rec.suggest_dataset_basename())
        self.assertEquals("xml", self.rec.suggest_extension("DAT"))

    def testMakeDatasetName(self):
        self.assertEquals("./SDSS_J115923.80+005905.16_GALAXY.xml", 
                          self.rec.make_dataset_filename())
        self.assertEquals("./goober.xml", 
                          self.rec.make_dataset_filename(base="goober"))
        self.assertEquals("./SDSS_J115923.80+005905.16_GALAXY.jpg", 
                          self.rec.make_dataset_filename(ext="jpg"))
        self.assertEquals("./goober.jpg", 
                          self.rec.make_dataset_filename(base="goober", 
                                                         ext="jpg"))
                          
        self.assertEquals(testdir+"/SDSS_J115923.80+005905.16_GALAXY.xml", 
                          self.rec.make_dataset_filename(testdir))

        path = os.path.join(testdir,self.base+".xml")
        self.assertFalse(os.path.exists(path))
        self.assertEquals(path, 
                          self.rec.make_dataset_filename(testdir, self.base))
        open(path,'w').close()
        self.assertTrue(os.path.exists(path))
        path = os.path.join(testdir,self.base+"-1.xml")
        self.assertEquals(path, 
                          self.rec.make_dataset_filename(testdir, self.base))
        open(path,'w').close()
        self.assertTrue(os.path.exists(path))
        path = os.path.join(testdir,self.base+"-2.xml")
        self.assertEquals(path, 
                          self.rec.make_dataset_filename(testdir, self.base))
        open(path,'w').close()
        self.assertTrue(os.path.exists(path))
        path = os.path.join(testdir,self.base+"-3.xml")
        self.assertEquals(path, 
                          self.rec.make_dataset_filename(testdir, self.base))
                         
        self.cleanfiles()
        open(os.path.join(testdir,self.base+".xml"),'w').close()
        path = os.path.join(testdir,self.base+"-1.xml")
        self.assertEquals(path, 
                          self.rec.make_dataset_filename(testdir, self.base))
        open(os.path.join(testdir,self.base+"-1.xml"),'w').close()
        open(os.path.join(testdir,self.base+"-2.xml"),'w').close()
        open(os.path.join(testdir,self.base+"-3.xml"),'w').close()
        path = os.path.join(testdir,self.base+"-4.xml")
        self.assertEquals(path, 
                          self.rec.make_dataset_filename(testdir, self.base))

        self.cleanfiles()
        self.assertEquals(os.path.join(testdir,self.base+".xml"),
                          self.rec.make_dataset_filename(testdir, self.base))



__all__ = "SSAServiceTest SSAQueryTest SSAResultsTest SSARecordTest SSAExecuteTest DatasetNameTest".split()
def suite():
    tests = []
    for t in __all__:
        tests.append(unittest.makeSuite(globals()[t]))
    return unittest.TestSuite(tests)

if __name__ == "__main__":
    srvr = testserver.TestServer(testserverport)
    try:
        srvr.start()
        unittest.main()
    finally:
        if srvr.isAlive():
            srvr.shutdown()
