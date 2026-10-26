import { describe, expect, it } from "vitest";
import { isValidEmail, suggestSlug, validate } from "../src/public/pages/RegisterPage";

const valid = {
  organisation_name: "Riverside Sports College",
  slug: "riverside-sports",
  academy_type: "sports-college",
  name: "Asha Rao",
  email: "asha@riverside.example.com",
  password: "Passw0rd!x",
  terms: true,
};

describe("validate (mirrors platform/tenancy POST /register rules)", () => {
  it("accepts a complete, valid form", () => {
    expect(validate(valid)).toEqual({});
  });

  it("reports every missing field on an empty form", () => {
    const e = validate({ organisation_name: "", slug: "", academy_type: "", name: "", email: "", password: "", terms: false });
    expect(Object.keys(e).sort()).toEqual(
      ["academy_type", "email", "name", "organisation_name", "password", "slug", "terms"].sort(),
    );
  });

  it("needs an organisation name of 2 to 200 characters, ignoring surrounding spaces", () => {
    expect(validate({ ...valid, organisation_name: " A " }).organisation_name).toBeTruthy();
    expect(validate({ ...valid, organisation_name: "AB" }).organisation_name).toBeUndefined();
    expect(validate({ ...valid, organisation_name: "x".repeat(201) }).organisation_name).toBeTruthy();
  });

  it.each(["ab", "Upper-Case", "has space", "under_score", "x".repeat(41)])("rejects the short name %j", (slug) => {
    expect(validate({ ...valid, slug }).slug).toBeTruthy();
  });

  it.each(["admin", "api", "www", "app", "platform"])("rejects the reserved short name %j", (slug) => {
    expect(validate({ ...valid, slug }).slug).toMatch(/reserved/);
  });

  it("accepts 3 to 40 lowercase letters, numbers and hyphens", () => {
    expect(validate({ ...valid, slug: "abc" }).slug).toBeUndefined();
    expect(validate({ ...valid, slug: "a1-b2-c3" }).slug).toBeUndefined();
    expect(validate({ ...valid, slug: "x".repeat(40) }).slug).toBeUndefined();
  });

  it("limits the administrator's name to 200 characters (identity_user.name)", () => {
    expect(validate({ ...valid, name: "x".repeat(200) }).name).toBeUndefined();
    expect(validate({ ...valid, name: "x".repeat(201) }).name).toBeTruthy();
  });

  it("rejects a password of only spaces", () => {
    expect(validate({ ...valid, password: "         " }).password).toBeTruthy();
  });

  it("asks for an email when it is empty, and for a valid one when it is malformed", () => {
    expect(validate({ ...valid, email: "  " }).email).toMatch(/Enter the administrator's email/);
    expect(validate({ ...valid, email: "asha@" }).email).toMatch(/valid email/);
  });

  it("requires an academy package, an administrator name, a valid email, an 8-character password and the terms", () => {
    expect(validate({ ...valid, academy_type: "" }).academy_type).toBeTruthy();
    expect(validate({ ...valid, name: "   " }).name).toBeTruthy();
    expect(validate({ ...valid, email: "not-an-email" }).email).toBeTruthy();
    expect(validate({ ...valid, password: "1234567" }).password).toBeTruthy();
    expect(validate({ ...valid, password: "12345678" }).password).toBeUndefined();
    expect(validate({ ...valid, terms: false }).terms).toBeTruthy();
  });
});

describe("isValidEmail (close to the server's email-validator)", () => {
  it.each([
    "asha@riverside.example.com",
    "first.last+admissions@college.edu.in",
    "o'brien@school.ac.uk",
    "  padded@example.org  ",
  ])("accepts %j", (email) => {
    expect(isValidEmail(email)).toBe(true);
  });

  it.each([
    "plain-text",
    "@example.com",
    "asha@",
    "asha@example",
    "asha@example.c",
    "asha@@example.com",
    "asha..rao@example.com",
    ".asha@example.com",
    "asha.@example.com",
    "asha rao@example.com",
    "asha@-example.com",
    "asha@example-.com",
    "asha@exa_mple.com",
    `${"a".repeat(65)}@example.com`,
    `asha@${"a".repeat(250)}.com`,
  ])("rejects %j", (email) => {
    expect(isValidEmail(email)).toBe(false);
  });
});

describe("suggestSlug", () => {
  it("lowercases and hyphenates the organisation name", () => {
    expect(suggestSlug("Riverside Sports College")).toBe("riverside-sports-college");
  });

  it("drops accents and punctuation and trims hyphens", () => {
    expect(suggestSlug("  École d'Art & Design!  ")).toBe("ecole-d-art-design");
  });

  it("never exceeds 40 characters or ends with a hyphen", () => {
    const s = suggestSlug("The Very Long Name Of A Performing Arts Academy In The City");
    expect(s.length).toBeLessThanOrEqual(40);
    expect(s.endsWith("-")).toBe(false);
  });

  it("produces a short name that passes validation for an ordinary name", () => {
    expect(validate({ ...valid, slug: suggestSlug("Riverside Sports College") }).slug).toBeUndefined();
  });
});
