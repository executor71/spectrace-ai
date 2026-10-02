import unittest,math
from retrieval_eval.metrics import evaluate,summarize,percentile,query_by_id
class MetricTests(unittest.TestCase):
    def test_all_relevant(self):
        value=evaluate([{'chunkId':'a'},{'chunkId':'b'}],{'a':2,'b':1});self.assertEqual(value['hitAt5'],1);self.assertEqual(value['recallAt5'],1);self.assertEqual(value['mrrAt5'],1);self.assertEqual(value['ndcgAt5'],1)
    def test_miss(self):
        value=evaluate([{'chunkId':'b'}],{'a':2,'b':0});self.assertEqual(value['hitAt5'],0);self.assertEqual(value['mrrAt5'],0);self.assertEqual(value['ndcgAt5'],0)
    def test_rank_two(self):self.assertEqual(evaluate([{'chunkId':'b'},{'chunkId':'a'}],{'a':2,'b':0})['mrrAt5'],.5)
    def test_recall_denominator(self):self.assertEqual(evaluate([{'chunkId':'a'}],{'a':2,'b':1})['recallAt5'],.5)
    def test_graded_dcg(self):self.assertAlmostEqual(evaluate([{'chunkId':'b'},{'chunkId':'a'}],{'a':2,'b':1})['ndcgAt5'],(1+3/math.log2(3))/(3+1/math.log2(3)))
    def test_empty_results(self):self.assertEqual(evaluate([],{'a':2})['hitAt5'],0)
    def test_empty_truth_not_perfect(self):self.assertIsNone(evaluate([],{})['recallAt5'])
    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):evaluate([{'chunkId':'a'}]*2,{'a':1})
    def test_unknown_chunk(self):
        with self.assertRaises(ValueError):evaluate([{'chunkId':'x'}],{'a':1})
    def test_truncated_at_five(self):self.assertEqual(evaluate([{'chunkId':str(n)} for n in range(6)],{str(n):int(n==5) for n in range(6)})['mrrAt5'],0)
    def test_percentile(self):self.assertEqual(percentile([1,2,3,4],.5),2.5);self.assertAlmostEqual(percentile([1,2,3,4],.95),3.85)
    def test_macro_average(self):self.assertEqual(summarize([evaluate([{'chunkId':'a'}],{'a':1}),evaluate([],{'a':1})],[10,20])['hitAt5'],.5)
    def test_unknown_query_id(self):
        with self.assertRaisesRegex(ValueError,'UNKNOWN_QUERY_ID'):query_by_id({'queries':[]},'missing')
if __name__=='__main__':unittest.main()
