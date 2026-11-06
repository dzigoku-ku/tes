import random
import unittest

import range_coding_demo as rc


class RangeCodingTest(unittest.TestCase):
    def roundtrip_int(self, msg):
        model = rc.scale_model(rc.FrequencyModel.from_message(msg))
        data, _ = rc.int_encode(msg, model)
        self.assertEqual(rc.int_decode(data, len(msg), model), msg)
        return data

    def roundtrip_exact(self, msg):
        model = rc.FrequencyModel.from_message(msg)
        low, high = rc.exact_encode(msg, model, verbose=False)
        code, _ = rc.shortest_binary_in(low, high)
        self.assertTrue(low <= code < high)
        self.assertEqual(rc.exact_decode(code, len(msg), model, verbose=False), msg)

    def test_examples(self):
        for msg in ["a", "aaaa", "abracadabra", "КОЛОКОЛ", "ИНТЕРВАЛЬНОЕ КОДИРОВАНИЕ"]:
            self.roundtrip_int(msg)
            self.roundtrip_exact(msg)

    def test_random(self):
        rng = random.Random(1)
        alphabets = ["ab", "abc", "abcdefghij", "".join(chr(1000 + i) for i in range(300))]
        for _ in range(500):
            alpha = rng.choice(alphabets)
            weights = [rng.random() ** 4 for _ in alpha]
            msg = "".join(rng.choices(alpha, weights=weights, k=rng.randint(1, 80)))
            self.roundtrip_int(msg)
            if len(msg) <= 40:
                self.roundtrip_exact(msg)

    def test_scaled_model(self):
        rng = random.Random(2)
        msg = "".join(rng.choices("ab", weights=[1, 1e-4], k=100_000)) + "b"
        model = rc.scale_model(rc.FrequencyModel.from_message(msg))
        self.assertLess(model.total, rc.MAX_TOTAL)
        self.roundtrip_int(msg)

    def test_close_to_entropy(self):
        rng = random.Random(3)
        msg = "".join(rng.choices("abcd", weights=[8, 4, 2, 1], k=20_000))
        model = rc.FrequencyModel.from_message(msg)
        data = self.roundtrip_int(msg)
        self.assertLess(len(data) * 8, len(msg) * model.entropy() * 1.001 + 64)


if __name__ == "__main__":
    unittest.main()
