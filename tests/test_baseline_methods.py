"""Pure deterministic source generation, without Lean, network or credentials."""
import unittest

from maam.baseline_methods import METHODS, generate
from maam.corpus import CorpusError
from maam.theory import digest


class BaselineMethodTests(unittest.TestCase):
    def request(self, proof, method='simpa_local_hypothesis'):
        return {'method': {'name': method}, 'incumbent': {'proof': proof},
                'request_sha256': 'a' * 64}

    def test_have_rewrite_exact_preserves_prefix_suffix_and_indentation(self):
        proof = ('by\n  intro g\n  have h1 : P := by\n'
                 '    have h0 := hf g.one g.one\n'
                 '    rw [g.one_mul] at h0\n    exact h0\n  exact h1\n')
        response, evidence = generate(self.request(proof))
        self.assertEqual(response['proof'],
            'by\n  intro g\n  have h1 : P := by\n'
            '    simpa only [g.one_mul] using (hf g.one g.one)\n  exact h1\n')
        self.assertEqual(evidence['line_span'], [4, 6])
        self.assertEqual(set(response), {'action', 'request_sha256', 'proof', 'bridge'})
        self.assertTrue(evidence['matched'])

    def test_reverse_rewrite_exact_with_final_line_without_newline(self):
        proof = 'by\n  intro h\n  rw [← hf x y]\n  exact h'
        response, evidence = generate(self.request(proof, 'simpa_rewrite_exact'))
        self.assertEqual(response['proof'],
                         'by\n  intro h\n  simpa only [hf x y] using (h)')
        self.assertEqual(evidence['line_span'], [3, 4])

    def test_only_first_matching_block_is_changed(self):
        block = '  have h := f x\n  rw [r] at h\n  exact h\n'
        response, evidence = generate(self.request('by\n' + block + block))
        self.assertEqual(response['proof'], 'by\n  simpa only [r] using (f x)\n' + block)
        self.assertEqual(evidence['line_span'], [2, 4])

    def test_identifier_and_indentation_must_match_exactly(self):
        for middle, last in [('  rw [r] at other', '  exact h'),
                             ('  rw [r] at h', '  exact other'),
                             ('   rw [r] at h', '  exact h'),
                             ('  rw [r] at h', '   exact h'),
                             ('  rw [r] at h_more', '  exact h'),
                             ('  rw [r] at h', '  exact h_more')]:
            with self.subTest(middle=middle, last=last):
                response, evidence = generate(self.request(
                    'by\n  have h := f x\n' + middle + '\n' + last))
                self.assertEqual(response['action'], 'retain')
                self.assertFalse(evidence['matched'])

    def test_comments_multiline_and_semicolon_syntax_are_not_rewritten(self):
        for proof, method in [
            ('by\n  have h := f x -- explanation\n  rw [r] at h\n  exact h',
             'simpa_local_hypothesis'),
            ('by\n/-\n  rw [← r]\n  exact h\n-/', 'simpa_rewrite_exact'),
            ('by\n  let text := "\n  rw [← r]\n  exact h\n"\n  exact old',
             'simpa_rewrite_exact'),
            ('by\n  have h := (f x\n  rw [r] at h\n  exact h',
             'simpa_local_hypothesis'),
            ('by\n  rw [← r]\n  exact (f x', 'simpa_rewrite_exact'),
            ('by\n  rw [← r, s]\n  exact h', 'simpa_rewrite_exact'),
            ('by\n  rw [← r]\n  exact h; assumption', 'simpa_rewrite_exact'),
            ('by\n  rw [r]\n  exact h', 'simpa_rewrite_exact')]:
            with self.subTest(proof=proof):
                response, evidence = generate(self.request(proof, method))
                self.assertEqual(response['action'], 'retain')
                self.assertIsNone(evidence['line_span'])

    def test_apostrophe_identifiers_rule_lists_and_crlf_are_supported(self):
        proof = "by\r\n  have h' := f (x, y)\r\n  rw [r, s] at h'\r\n  exact h'\r\n"
        response, evidence = generate(self.request(proof))
        self.assertEqual(response['proof'],
                         'by\r\n  simpa only [r, s] using (f (x, y))\r\n')
        self.assertEqual(evidence['line_span'], [2, 4])

    def test_replay_is_deterministic_and_byte_hashes_are_exact(self):
        request = self.request('by\n  rw [← r]\n  exact ⟨h, h⟩\n', 'simpa_rewrite_exact')
        response, evidence = generate(request)
        self.assertEqual(generate(request), (response, evidence))
        self.assertEqual(evidence['before_proof_sha256'],
                         digest(request['incumbent']['proof'].encode()))
        self.assertEqual(evidence['after_proof_sha256'], digest(response['proof'].encode()))
        self.assertEqual(evidence['before_proof_bytes'],
                         len(request['incumbent']['proof'].encode()))
        self.assertEqual(evidence['after_proof_bytes'], len(response['proof'].encode()))
        self.assertNotIn('proof_source_tokens', evidence)
        self.assertNotIn('verified', evidence)

    def test_no_match_retains_without_claiming_exhaustion_or_validity(self):
        proof = 'by\n  exact old_proof'
        response, evidence = generate(self.request(proof))
        self.assertEqual(set(response), {'action', 'request_sha256', 'reason'})
        self.assertEqual(response['action'], 'retain')
        self.assertIn('no matching supported source pattern', response['reason'])
        self.assertIn('not evidence of search exhaustion', response['reason'])
        self.assertEqual(evidence['before_proof_sha256'], evidence['after_proof_sha256'])
        self.assertEqual(evidence['before_proof_bytes'], evidence['after_proof_bytes'])

    def test_unknown_method_and_malformed_requests_fail_explicitly(self):
        self.assertEqual(set(METHODS), {'simpa_local_hypothesis', 'simpa_rewrite_exact'})
        valid = self.request('by exact h')
        for request in [None, {}, {**valid, 'method': 'not an object'},
                        {**valid, 'method': {'name': 'guess'}},
                        {**valid, 'method': {'name': []}},
                        {**valid, 'incumbent': {'proof': 3}},
                        {**valid, 'incumbent': {'proof': ''}},
                        {**valid, 'request_sha256': 'unbound'}]:
            with self.subTest(request=request), self.assertRaises(CorpusError):
                generate(request)


if __name__ == '__main__':
    unittest.main()
