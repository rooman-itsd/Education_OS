# ELMO schemas (vendored test fixtures)

- Source: https://github.com/emrex-eu/elmo-schemas, tag `v2.1.2` (`schema.xsd`, `example.xml`, `references/`)
- Licence: MIT, Copyright (c) 2022 ELMO (file `LICENSE` here, from the repository; the repository also carries `LICENSE.txt`)
- `references/xml.xsd` is the W3C `xml:` namespace schema (https://www.w3.org/2001/03/xml.xsd);
  `references/ewp-address.xsd` and `references/ewp-common-types.xsd` are from https://github.com/erasmus-without-paper
  (`ewp-specs-types-address` and `ewp-specs-architecture`, tag `stable-v1`, CC BY-SA licensed by the EWP project; they are
  `import`ed by schema.xsd and carried only so validation needs no network).
- The only change: each `schemaLocation` in `schema.xsd` (and the two EWP files) that pointed at a URL now points at the
  copy under `references/`, so `xmllint --nonet` validates offline. Nothing else is edited.

Validate: `cd tests/fixtures/elmo-schemas && xmllint --noout --nonet --schema schema.xsd <file>`.
