/*
 * QuickAdd user script: New Service Request (smart)
 *
 * Wired into the "New Service Request" QuickAdd macro. Flow:
 *   1. Pick the customer from a suggester over Companies/
 *   2. Derive the SR code from that company's `code:` frontmatter
 *      (falls back to an input prompt if the company has no code)
 *   3. Prompt for a short title
 *   4. Pick a contact from People/ whose `company` links to that customer
 *      (or "none", or type a free-text name)
 *   5. Optionally link a Project from Projects/ whose `client` is that customer
 *   6. Optional description
 *   7. Create  Service Requests/<CODE><YYYYMMDD>-<title>/Initial Request.md
 *      from Templates/Service Request Template.md, then open it.
 *
 * No Templater dependency — the template's {{VALUE:...}} / {{DATE:...}}
 * tokens are substituted here so the same template still works for the
 * plain "New Service Request (manual)" Template choice.
 */

const TEMPLATE_PATH = "Templates/Service Request Template.md";
const SR_ROOT = "Service Requests";
const COMPANIES_ROOT = "Companies/";
const PEOPLE_ROOT = "People/";
const PROJECTS_ROOT = "Projects/";

module.exports = async (params) => {
	const { app, quickAddApi: qa } = params;

	// 1. Customer -------------------------------------------------------------
	const companyFiles = app.vault
		.getMarkdownFiles()
		.filter((f) => f.path.startsWith(COMPANIES_ROOT))
		.sort((a, b) => a.basename.localeCompare(b.basename));

	if (companyFiles.length === 0) {
		throw new Error(
			`No notes in ${COMPANIES_ROOT} — add a company first (QuickAdd: Add Company).`,
		);
	}

	const companyFile = await qa.suggester(
		companyFiles.map((f) => f.basename),
		companyFiles,
	);
	if (!companyFile) return; // cancelled
	const customer = companyFile.basename;

	// 2. Code ---------------------------------------------------------------
	const companyFm =
		app.metadataCache.getFileCache(companyFile)?.frontmatter ?? {};
	let code = (companyFm.code ?? "").toString().trim();
	if (!code) {
		code = (
			(await qa.inputPrompt(
				`"${customer}" has no code: in frontmatter — enter a short code (e.g. CAH)`,
			)) ?? ""
		).trim();
		if (!code) throw new Error("A code is required to name the SR folder.");
	}

	// 3. Title ------------------------------------------------------------
	const rawTitle = (
		(await qa.inputPrompt("Service Request — short title")) ?? ""
	).trim();
	if (!rawTitle) return; // cancelled / empty
	const safeTitle = rawTitle
		.replace(/[\\/:*?"<>|]/g, "-")
		.replace(/\s+/g, " ")
		.trim();

	// 4. Contact --------------------------------------------------------
	const NONE = "— none —";
	const OTHER = "— type a name —";
	const people = app.vault
		.getMarkdownFiles()
		.filter((f) => f.path.startsWith(PEOPLE_ROOT))
		.filter((f) => {
			const c =
				app.metadataCache.getFileCache(f)?.frontmatter?.company ?? "";
			return c.toString().includes(customer);
		})
		.sort((a, b) => a.basename.localeCompare(b.basename));

	const contactChoices = [NONE, ...people.map((f) => f.basename), OTHER];
	const picked = await qa.suggester(contactChoices, contactChoices);
	if (picked === undefined) return; // cancelled
	let contact = "";
	if (picked === OTHER) {
		contact = ((await qa.inputPrompt("Contact name")) ?? "").trim();
	} else if (picked !== NONE) {
		contact = picked;
	}

	// 5. Project (optional) ------------------------------------------
	const P_NONE = "— none —";
	const projects = app.vault
		.getMarkdownFiles()
		.filter((f) => f.path.startsWith(PROJECTS_ROOT))
		.filter((f) => {
			const c =
				app.metadataCache.getFileCache(f)?.frontmatter?.client ?? "";
			return c.toString().includes(customer);
		})
		.sort((a, b) => a.basename.localeCompare(b.basename));

	let project = "";
	if (projects.length) {
		const projChoices = [P_NONE, ...projects.map((f) => f.basename)];
		const pickedProj = await qa.suggester(projChoices, projChoices);
		if (pickedProj === undefined) return; // cancelled
		if (pickedProj !== P_NONE) project = pickedProj;
	}

	// 7. Description --------------------------------------------------
	const description = (
		(await qa.wideInputPrompt("Description (optional)")) ?? ""
	).trim();

	// 8. Dates ------------------------------------------------------
	const now = new Date();
	const pad = (n) => String(n).padStart(2, "0");
	const y = now.getFullYear();
	const m = pad(now.getMonth() + 1);
	const d = pad(now.getDate());
	const stamp = `${y}${m}${d}`;
	const opened = `${y}-${m}-${d}`;

	// 9. Paths ----------------------------------------------------
	const folder = `${SR_ROOT}/${code}${stamp}-${safeTitle}`;
	const notePath = `${folder}/Initial Request.md`;
	if (app.vault.getAbstractFileByPath(notePath)) {
		throw new Error(`${notePath} already exists.`);
	}

	// 10. Render template ---------------------------------------
	const tplFile = app.vault.getAbstractFileByPath(TEMPLATE_PATH);
	if (!tplFile) throw new Error(`Missing ${TEMPLATE_PATH}`);
	let body = await app.vault.read(tplFile);
	body = body
		.split("{{VALUE:customer}}").join(customer)
		.split("{{VALUE:contact}}").join(contact)
		.split("{{VALUE:description}}").join(description)
		.split("{{DATE:YYYY-MM-DD}}").join(opened);
	if (!contact) body = body.replace('contact: "[[]]"', "contact:");
	if (project) body = body.replace(/^project:\s*$/m, `project: "[[${project}]]"`);

	// 11. Create -----------------------------------------------
	if (!app.vault.getAbstractFileByPath(folder)) {
		await app.vault.createFolder(folder);
	}
	const file = await app.vault.create(notePath, body);

	// 12. Open ----------------------------------------------
	await app.workspace.getLeaf(false).openFile(file);
};
