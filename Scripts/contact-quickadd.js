/*
 * QuickAdd user script: Add Contact (smart)
 *
 * Wired into the "Add Contact" QuickAdd macro. Flow:
 *   1. Prompt for the contact's name
 *   2. Pick the company from a suggester over Companies/
 *      - "— none —"              leaves company blank
 *      - "— add new company —"   prompts for name / phone / code and
 *                                creates Companies/<name>.md from the
 *                                Company Template before continuing
 *   3. Optional phone + email
 *   4. Create People/<name>.md from Templates/Person Template.md, then open it.
 *
 * No Templater dependency — the template's {{VALUE:...}} tokens are
 * substituted here so the same template still works for a plain Template choice.
 */

const PERSON_TEMPLATE_PATH = "Templates/Person Template.md";
const COMPANY_TEMPLATE_PATH = "Templates/Company Template.md";
const PEOPLE_ROOT = "People/";
const COMPANIES_ROOT = "Companies/";

const sanitize = (s) =>
	s
		.replace(/[\\/:*?"<>|]/g, "-")
		.replace(/\s+/g, " ")
		.trim();

module.exports = async (params) => {
	const { app, quickAddApi: qa } = params;

	// 1. Contact name -------------------------------------------------------
	const rawName = ((await qa.inputPrompt("Contact — full name")) ?? "").trim();
	if (!rawName) return; // cancelled / empty
	const name = sanitize(rawName);

	const notePath = `${PEOPLE_ROOT}${name}.md`;
	if (app.vault.getAbstractFileByPath(notePath)) {
		throw new Error(`${notePath} already exists.`);
	}

	// 2. Company ----------------------------------------------------------
	const NONE = "— none —";
	const ADD_NEW = "— add new company —";
	const companyFiles = app.vault
		.getMarkdownFiles()
		.filter((f) => f.path.startsWith(COMPANIES_ROOT))
		.sort((a, b) => a.basename.localeCompare(b.basename));

	const companyChoices = [NONE, ...companyFiles.map((f) => f.basename), ADD_NEW];
	const picked = await qa.suggester(companyChoices, companyChoices);
	if (picked === undefined) return; // cancelled

	let company = "";
	if (picked === ADD_NEW) {
		company = await createCompany(app, qa);
		if (!company) return; // cancelled out of the new-company flow
	} else if (picked !== NONE) {
		company = picked;
	}

	// 3. Phone + email --------------------------------------------------
	const phone = ((await qa.inputPrompt("Phone (optional)")) ?? "").trim();
	const email = ((await qa.inputPrompt("Email (optional)")) ?? "").trim();

	// 4. Render person template --------------------------------------
	const tplFile = app.vault.getAbstractFileByPath(PERSON_TEMPLATE_PATH);
	if (!tplFile) throw new Error(`Missing ${PERSON_TEMPLATE_PATH}`);
	let body = await app.vault.read(tplFile);
	body = body
		.split("{{VALUE:company}}").join(company)
		.split("{{VALUE:phone}}").join(phone)
		.split("{{VALUE:email}}").join(email);
	if (!company) body = body.replace('company: "[[]]"', "company:");

	// 5. Create + open ---------------------------------------------
	if (!app.vault.getAbstractFileByPath(PEOPLE_ROOT.replace(/\/$/, ""))) {
		await app.vault.createFolder(PEOPLE_ROOT.replace(/\/$/, ""));
	}
	const file = await app.vault.create(notePath, body);
	await app.workspace.getLeaf(false).openFile(file);
};

/**
 * Prompt for a new company's details, create Companies/<name>.md from the
 * Company Template, and return its basename (or "" if the user cancelled).
 */
async function createCompany(app, qa) {
	const rawCompany = (
		(await qa.inputPrompt("New company — name")) ?? ""
	).trim();
	if (!rawCompany) return "";
	const company = sanitize(rawCompany);

	const companyPath = `${COMPANIES_ROOT}${company}.md`;
	if (app.vault.getAbstractFileByPath(companyPath)) {
		// Already exists — just link to it rather than erroring.
		return company;
	}

	const phone = ((await qa.inputPrompt("Company phone (optional)")) ?? "").trim();
	const code = (
		(await qa.inputPrompt("Company code — short prefix for SRs, e.g. CAH (optional)")) ??
		""
	).trim();

	const tplFile = app.vault.getAbstractFileByPath(COMPANY_TEMPLATE_PATH);
	if (!tplFile) throw new Error(`Missing ${COMPANY_TEMPLATE_PATH}`);
	let body = await app.vault.read(tplFile);
	body = body
		.split("{{VALUE:phone}}").join(phone)
		.split("{{VALUE:code}}").join(code);
	if (!code) body = body.replace(/^code:.*\n/m, "");

	if (!app.vault.getAbstractFileByPath(COMPANIES_ROOT.replace(/\/$/, ""))) {
		await app.vault.createFolder(COMPANIES_ROOT.replace(/\/$/, ""));
	}
	await app.vault.create(companyPath, body);
	return company;
}
