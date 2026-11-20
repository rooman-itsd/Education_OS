/*
 * DRAFT: REQUIRES LEGAL REVIEW BEFORE PUBLICATION.
 *
 * The Privacy Notice and Terms of Service of the public site (#/privacy, #/terms), issue #148 (DPDP pass).
 * Written from the data map in docs/architecture/dpdp-pass-2026-11.md, not by a lawyer. Counsel must review both
 * before the launch. Company, Grievance Officer, hosting and jurisdiction were given by Faizan on 20 Nov 2026;
 * [Registered address] is still a placeholder, shown as it is until he fills it.
 *
 * LEGAL_VERSION must equal platform/tenancy's DEFAULT_TERMS_VERSION (eos_tenancy/application/service.py,
 * #665): registration records that version as the one the administrator accepted. Change both together when
 * either document changes.
 */

/** Version of both documents, recorded by platform/tenancy at registration (terms_version). */
export const LEGAL_VERSION = "2026-11-20";
/** Shown as the effective date. Set to the publication date after legal review. */
export const LEGAL_EFFECTIVE = "20 November 2026";

/** The operator's details, given by Faizan (20 Nov 2026). ADDRESS is still a visible placeholder. */
export const COMPANY = "Rooman Technologies Pvt. Ltd.";
export const ADDRESS = "[Registered address]";
export const GRIEVANCE_OFFICER = "Faizan, faizan@rooman.com";

/** A block of a section: a paragraph, or a bulleted list. */
export type LegalBlock = string | { list: string[] };

export interface LegalSection {
  id: string;
  heading: string;
  blocks: LegalBlock[];
}

export interface LegalDocument {
  title: string;
  summary: string;
  sections: LegalSection[];
}

export const PRIVACY_NOTICE: LegalDocument = {
  title: "Privacy Notice",
  summary:
    "What personal data Education OS holds, why, on what legal basis, who it is shared with, how long it is kept, " +
    "and how to use your rights under India's Digital Personal Data Protection Act, 2023.",
  sections: [
    {
      id: "who-we-are",
      heading: "1. Who we are and what this notice covers",
      blocks: [
        `Education OS is operated by ${COMPANY}, ${ADDRESS} ("we", "us").`,
        "We play two different roles under the Digital Personal Data Protection Act, 2023 (DPDP Act):",
        {
          list: [
            "For the account of an organisation and its administrators, for billing, for the emails we send and for " +
              "visitors to this website, we decide why and how the data is used: we are the Data Fiduciary, and this " +
              "notice is our notice to you.",
            "For the data an institution keeps in Education OS about its own students, applicants, staff, parents " +
              "and other people, the institution is the Data Fiduciary and we are its Data Processor. We process that " +
              "data only to run the service for the institution and on its instructions. The institution's own " +
              "privacy notice tells those people how it uses their data; section 8 explains how to reach it.",
          ],
        },
      ],
    },
    {
      id: "what-we-collect",
      heading: "2. Personal data we collect",
      blocks: [
        "When an organisation registers:",
        {
          list: [
            "the organisation's name, short name, academy package and, if given, country;",
            "the first administrator's full name, work email address and password (we store only a salted hash of " +
              "the password, never the password itself);",
            "a record that the administrator accepted these Terms and read this notice: the version, the time and " +
              "the user who accepted them.",
          ],
        },
        "When people use the platform:",
        {
          list: [
            "user accounts: name, email address, roles, account status and, for single sign-on, the identifier the " +
              "institution's sign-in provider gives the person;",
            "a sign-in token kept in the browser's local storage until the person signs out or it expires (12 hours);",
            "a record of actions taken (who did what, and when), kept for security and accountability.",
          ],
        },
        "For billing: the plan and subscription, invoices (including the organisation's legal name, GSTIN, billing " +
          "address and state) and the payment gateway's reference for each payment. We never receive card numbers, " +
          "bank passwords or UPI PINs.",
        "For the emails we send: the recipient's address, the message and whether it was delivered.",
        "When you visit this website: our web server records your IP address, the time, the page requested and your " +
          "browser's user agent in its access logs. The site loads its fonts from Google Fonts, so your browser also " +
          "sends your IP address to Google. The site sets no cookies and uses no analytics or advertising trackers.",
        "Data institutions keep in Education OS, depending on the modules they use, can include: names, dates of " +
          "birth, gender, national ID or passport numbers, contact details and guardians' details of students and " +
          "applicants; enrolment, courses, timetables, attendance, assessments, submissions and grades; fee invoices, " +
          "payments and concessions; staff records, salary structures, payslips, leave, appraisals and the last four " +
          "digits of bank accounts and PAN; hostel, library and transport records, including a vehicle's location " +
          "during a trip; athletes' profiles, fitness results, injuries, clinical notes and nutrition plans; " +
          "grievances, including complaints of sexual harassment and ragging; right-to-information requests; " +
          "helpdesk tickets; alumni contact details; and documents people upload.",
      ],
    },
    {
      id: "purposes",
      heading: "3. Why we use it, and our legal basis",
      blocks: [
        {
          list: [
            "To create and run the organisation's account, sign people in and keep the service working: the consent " +
              "given at registration (section 6 of the DPDP Act) and the data the administrator provides for that " +
              "purpose (section 7(a)).",
            "To keep the service secure, prevent misuse and keep an audit trail: the same consent, and the legitimate " +
              "uses the DPDP Act allows.",
            "To issue GST tax invoices and keep accounts: compliance with Indian law (section 7).",
            "To send service emails (verification, approval, trial reminders, invoices and the notifications the " +
              "organisation turns on): the consent given at registration.",
            "Data institutions keep in Education OS: processed only to provide the service to that institution. The " +
              "institution decides the purpose and the legal basis (usually the consent of the person, or of a parent " +
              "or guardian for a child).",
          ],
        },
        "We do not sell personal data, use it for advertising, or use it to train models for anyone else.",
      ],
    },
    {
      id: "children",
      heading: "4. Children's personal data",
      blocks: [
        "Institutions using Education OS may have students under 18. Under section 9 of the DPDP Act the institution, " +
          "as Data Fiduciary, must obtain the verifiable consent of a parent or lawful guardian before processing a " +
          "child's personal data, except where the law exempts it. Our Terms of Service require institutions to do so.",
        "We do not track children, monitor their behaviour, or direct advertising at them, and Education OS shows no " +
          "advertising. Only an adult may register an organisation.",
      ],
    },
    {
      id: "sharing",
      heading: "5. Who we share it with",
      blocks: [
        "We share personal data only with the service providers we need to run Education OS, under contracts that " +
          "limit them to that purpose:",
        {
          list: [
            "Hosting: Education OS runs on servers we operate ourselves, in India (Bengaluru). Database backups are " +
              "copied to a second location we control.",
            "Email: an email delivery service that sends the platform's emails.",
            "Payments: SBIePay (State Bank of India's payment gateway) for paid plans, and for fee payments where an " +
              "institution turns it on.",
            "Fonts: Google Fonts, which receives the IP address of visitors to this website and of the app.",
          ],
        },
        "If an institution turns them on, Education OS also exchanges data with: DigiLocker; the National Academic " +
          "Depository and the Academic Bank of Credits; the AISHE, NIRF and NAAC portals; video conferencing " +
          "services (Zoom, Microsoft Teams, Webex or Jitsi); partner universities for transcript exchange; and, only " +
          "when an athlete links their own account, wearable services (Garmin, Polar, Fitbit or Strava). The " +
          "institution chooses these; a person's consent is asked where the service requires it.",
        "We disclose personal data to a government authority or court only when Indian law requires us to.",
      ],
    },
    {
      id: "transfers",
      heading: "6. Transfers outside India",
      blocks: [
        "Some of the providers above (Google Fonts, and the video conferencing and wearable services an institution " +
          "may turn on) can process data outside India. Section 16 of the DPDP Act allows this except to countries the " +
          "Central Government restricts; we will stop any transfer to such a country.",
      ],
    },
    {
      id: "retention",
      heading: "7. How long we keep it",
      blocks: [
        {
          list: [
            "While an organisation's account is open, we keep its data so the service works. Institutions decide how " +
              "long they keep their own records.",
            "When an organisation asks us to close its account, we archive it at once (nobody can sign in) and delete " +
              "all of its data 30 days later. Until then the closure can be undone.",
            "Deleted data leaves our database backups within 8 weeks, as the backups rotate.",
            "The audit trail is kept for up to 7 years. It never holds email addresses or phone numbers, and once an " +
              "organisation is deleted its entries keep only who did what and when, without the data itself.",
            "Records of events between parts of the platform are deleted 30 days after they are processed.",
            "Tax invoices are kept for as long as Indian tax law requires.",
          ],
        },
      ],
    },
    {
      id: "rights",
      heading: "8. Your rights and how to use them",
      blocks: [
        "Under the DPDP Act you have the right to:",
        {
          list: [
            "get a summary of your personal data we process and of what we do with it, and who we have shared it with;",
            "have your personal data corrected, completed, updated or erased;",
            "withdraw your consent at any time (this does not affect what was done before, and some of the service " +
              "may stop working for you);",
            "have a grievance about how we handle your data answered; and",
            "nominate someone to use these rights for you if you die or cannot use them yourself.",
          ],
        },
        "If you are a student, applicant, parent or staff member of an institution, your institution decides how your " +
          "data in Education OS is used: send your request to the institution first. We help institutions answer " +
          "such requests, and will pass on any request sent to us.",
        `For anything else, write to our Grievance Officer: ${GRIEVANCE_OFFICER}. We will confirm who you are ` +
          "before acting on a request, and aim to answer within 30 days.",
        "If you are not satisfied with our answer, you can complain to the Data Protection Board of India.",
      ],
    },
    {
      id: "security",
      heading: "9. How we protect it",
      blocks: [
        "Connections to Education OS are encrypted (HTTPS). Passwords are stored only as salted hashes. Every " +
          "organisation's data is kept apart from every other's by the database itself, and inside an organisation " +
          "each role sees only what it needs. Our platform administrators can open an organisation's account for " +
          "support only with a stated reason, and every such access is recorded.",
        "If a personal data breach happens, we will tell the affected institutions, the people affected and the Data " +
          "Protection Board as the DPDP Act and its Rules require.",
      ],
    },
    {
      id: "contact",
      heading: "10. Contact",
      blocks: [`${COMPANY}, ${ADDRESS}. Grievance Officer: ${GRIEVANCE_OFFICER}.`],
    },
    {
      id: "changes",
      heading: "11. Changes to this notice",
      blocks: [
        "When we change this notice we publish the new version here with a new version number, and tell organisation " +
          "administrators by email before a significant change takes effect.",
      ],
    },
  ],
};

export const TERMS_OF_SERVICE: LegalDocument = {
  title: "Terms of Service",
  summary:
    "The agreement between the operator of Education OS and every organisation that registers: your account, " +
    "acceptable use, plans and the free trial, invoicing, your data, availability, liability and closing your account.",
  sections: [
    {
      id: "agreement",
      heading: "1. The agreement",
      blocks: [
        `These Terms are an agreement between ${COMPANY}, ${ADDRESS} ("we", "us") and the organisation that ` +
          'registers for Education OS ("you"). The person who registers accepts them on the organisation\'s behalf ' +
          "and confirms that they are at least 18 and may bind the organisation.",
        "Our Privacy Notice explains how we handle personal data and is part of these Terms.",
      ],
    },
    {
      id: "account",
      heading: "2. Your account",
      blocks: [
        {
          list: [
            "Give accurate details when you register and keep them up to date.",
            "Your administrator's email address must be verified, and we review every new organisation before it " +
              "goes live. We may decline a registration.",
            "Keep passwords secret. You are responsible for the users you create, the roles you give them and what " +
              "they do in your account.",
            "Tell us at once if you think someone has got into your account.",
          ],
        },
      ],
    },
    {
      id: "plans",
      heading: "3. Plans, the free trial and fees",
      blocks: [
        {
          list: [
            "Every organisation starts on the free Trial for 30 days: the common platform and one specialised suite, " +
              "for up to 25 staff users, 500 students and 2 GB of storage.",
            "When the trial ends your account becomes read-only until you choose a paid plan: you can still see and " +
              "export your data, but not change it.",
            "Paid plans (Standard and Premium) are charged monthly at the prices on our plans page when you choose " +
              "them, in Indian rupees. Each plan has its own modules, integrations and limits; we may refuse to add " +
              "users beyond your plan's limit.",
            "We issue a GST tax invoice for every billing period, with GST at the applicable rate shown on it. " +
              "Payments are made through SBIePay.",
            "We may change prices for future billing periods; we will tell your administrators before a change " +
              "applies to you.",
            "If a payment is not made we may limit your account to reading until it is.",
          ],
        },
      ],
    },
    {
      id: "acceptable-use",
      heading: "4. Acceptable use",
      blocks: [
        "You must not, and must not let your users:",
        {
          list: [
            "break any law, or store or send content that is unlawful, infringes someone's rights or harms children;",
            "put personal data into Education OS that you have no right to process;",
            "try to reach another organisation's data, test our security without our written permission, or disrupt " +
              "or overload the service;",
            "copy, resell or reverse engineer the service, except as the law allows;",
            "use the service to send spam or unsolicited messages.",
          ],
        },
        "We may suspend an account that breaks these rules, and will tell you why unless the law prevents us.",
      ],
    },
    {
      id: "your-data",
      heading: "5. Your data, and our role in processing it",
      blocks: [
        "Your data stays yours. For the personal data of your students, applicants, staff, parents and others that you " +
          "keep in Education OS, you are the Data Fiduciary under the Digital Personal Data Protection Act, 2023, and " +
          "we are your Data Processor. You must:",
        {
          list: [
            "give those people a privacy notice and have a valid legal basis, usually their consent, for what you do " +
              "with their data;",
            "obtain the verifiable consent of a parent or lawful guardian before processing the data of a child under " +
              "18, where section 9 of the Act requires it;",
            "answer their requests to see, correct or erase their data, and their grievances.",
          ],
        },
        "We will:",
        {
          list: [
            "process that data only to provide the service and on your instructions;",
            "keep it confidential, and bind our staff and service providers to do the same;",
            "keep reasonable security safeguards in place;",
            "tell you without undue delay if we become aware of a personal data breach affecting your data;",
            "help you answer the requests of the people your data is about;",
            "use only the service providers listed in our Privacy Notice, and tell you before we add one;",
            "delete your data when your account is closed, as section 8 below describes.",
          ],
        },
      ],
    },
    {
      id: "availability",
      heading: "6. Availability and support",
      blocks: [
        "We work to keep Education OS available and back up its database every night, but we do not promise " +
          "uninterrupted service unless we agree a service level with you in writing. We may take the service down " +
          "for maintenance, and will warn you in advance when we can.",
      ],
    },
    {
      id: "closing",
      heading: "7. Suspension and closing your account",
      blocks: [
        {
          list: [
            "You may close your account at any time by asking us in writing.",
            "We may suspend or close your account if you break these Terms, do not pay, or if the law requires it.",
          ],
        },
      ],
    },
    {
      id: "export-and-deletion",
      heading: "8. Exporting and deleting your data",
      blocks: [
        {
          list: [
            "Before your account closes, ask us for an export: a complete copy of your organisation's data in a " +
              "machine-readable format (JSON).",
            "When your account closes it is archived at once and nobody can sign in. We delete all of its data 30 " +
              "days later; within those 30 days you can ask us to restore it.",
            "Deleted data leaves our backups within 8 weeks. We keep what Indian law requires us to keep, such as tax " +
              "invoices, for as long as it requires.",
          ],
        },
      ],
    },
    {
      id: "ownership",
      heading: "9. Our software",
      blocks: [
        "We own Education OS and its software. While your subscription lasts we give you a non-exclusive, " +
          "non-transferable right to use it for your organisation. If you send us suggestions, we may use them freely.",
      ],
    },
    {
      id: "liability",
      heading: "10. Warranties and liability",
      blocks: [
        "Apart from what these Terms promise, the service is provided as it is. To the extent the law allows, we are " +
          "not liable for indirect or consequential loss, or for lost profits or data you could have exported, and our " +
          "total liability for any claim is limited to the fees you paid us in the 12 months before it arose. Nothing " +
          "here limits a liability that the law does not allow to be limited.",
      ],
    },
    {
      id: "changes",
      heading: "11. Changes to these Terms",
      blocks: [
        "We may change these Terms. We will publish the new version here with a new version number and tell your " +
          "administrators by email before a significant change takes effect.",
      ],
    },
    {
      id: "law",
      heading: "12. Governing law",
      blocks: [
        "These Terms are governed by the laws of India. The courts at Bengaluru, Karnataka have exclusive jurisdiction " +
          "over any dispute about them.",
      ],
    },
    {
      id: "contact",
      heading: "13. Contact",
      blocks: [`${COMPANY}, ${ADDRESS}. Grievance Officer: ${GRIEVANCE_OFFICER}.`],
    },
  ],
};
