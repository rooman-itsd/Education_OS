# Europass Digital Credentials fixtures (vendored for tests)

- Source: https://github.com/european-commission-empl/European-Learning-Model (branch `master`, retrieved 5 Nov 2026)
  - `EDC-generic-no-cv.ttl`, `EDC-generic-full.ttl`: SHACL shapes of the EDC application profile (`rdf/ap/edc/`);
    `edc-generic-full` is the shape a credential names in its `credentialSchema`
  - `edc-ap-context.jsonld`: the JSON-LD context http://data.europa.eu/snb/model/context/edc-ap (`rdf/ap/edc/edc-ap-context.jsonld`)
  - `Sample-CertOfPart-unsigned.jsonld`: the Commission's sample unsigned credential (`Credentials/JSON-LD Examples (ELM v3)/`)
- Licence: EUPL-1.2 for the repository (`LICENSE-EUPL-1.2.txt` here); the shapes and context files carry CC BY 4.0
  (`dc:license <https://creativecommons.org/licenses/by/4.0/>`) in their own headers.
- Unmodified.

There is no published JSON Schema for EDC; the credential is validated with SHACL. No SHACL engine is on the approved
stack, so `tests/edc_shacl.py` checks cardinality (minCount and maxCount of every property, per class) against these
shapes, and that every key is a term of the JSON-LD context. It is calibrated against the Commission's sample: the only
shape the sample violates is `cred:issued`, which the issuer adds when it seals the credential.
