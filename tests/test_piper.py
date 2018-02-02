from unittest import TestCase

from miniutils.piper import mp_pipeline as piper

import operator as op

# TODO: Implement tests for piper


# class TestMPPipeline(TestCase):
#     def test_wordcount(self):
#         sentences = ["Hello world", "How are you?"]
#         splitter = piper.Map(str.split)
#         lenner = piper.Map(len, previous_element=splitter)
#         summer = piper.Reduce(op.add, 0, previous_element=lenner)
#         pipeline = piper.Pipeline(splitter, summer, single_output=True)
#         print(pipeline.graphviz())
#         pipeline.start()
#
#         pipeline.put_all(*sentences)
#         pipeline.finish()
#
#         results = list(pipeline)
#         self.assertListEqual(results, [5])
#
#     def test_many(self):
#         import random, math, functools
#         num = 10
#         sequence = (random.gauss(0, 1) for _ in range(num))
#         sqr = lambda x: x ** 2
#
#         pipe = piper.Source()
#         pipe = pipe.map(sqr, nprocs=2)
#         pipe = pipe.progbar(total=num)
#         pipe = pipe.map(math.sqrt, nprocs=2)
#         pipe = pipe.map(sqr, nprocs=2)
#         pipe = pipe.map(math.sqrt, nprocs=2)
#         pipe = pipe.map(sqr, nprocs=2)
#         pipe = pipe.map(math.sqrt, nprocs=2)
#         pipe = pipe.map(sqr, nprocs=2)
#         pipe = pipe.map(math.sqrt, nprocs=2)
#         pipe = pipe.map(sqr, nprocs=2)
#         pipe = pipe.reduce(sum, 0, nprocs=2)
#         pipe = pipe.map(lambda x: x / num, single_output=True)
#         print(pipe.graphviz())
#         pipe.start()
#
#         for n in sequence:
#             pipe.put(n)
#         pipe.finish()
#
#         results = list(pipe)
#         self.assertEqual(len(results), 1)
#         result = int(results[0] * 10000)
#
#         self.assertEqual(result, 0)

