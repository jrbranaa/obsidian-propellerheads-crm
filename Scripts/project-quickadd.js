/*
 * QuickAdd user script: New Project
 *
 * Wired into the "New Project" QuickAdd macro. Flow:
 *   1. Prompt for the project name
 *   2. Pick the client from a suggester over Companies/
 *   3. Pick a contact from that client's People/ (or none / free text)
 *   4. Pick a billing model (hourly / fixed / not-to-exceed)
 *   5. Prompt quote/cap and/or budget hours as the model warrants
 *   6. Opened date (defaults today), optional scope
 *   7. Create Projects/<name>.md from Templates/Project Template.md, then open it.
 *
 * Child Service Requests link back via their `project:` frontmatter — set by
 * Scripts/sr-quickadd.js or by hand. This note owns scope + the rollup, not work.
 */

const TEMPLATE_PATH = "Templates/Project Template.md";
const PROJECTS_ROOT = "Projects";
const COMPANIES_ROOT = "Companies/";
const PEOPLE_ROOT = "People/";

module.exports = async (params) => {
	const { app, quickAddApi: qa } = params;

	// 1. Name -------------------------------------------------------------
	const rawName = ((await qa.inputPrompt("Project — name")) ?? "").trim();
	if (!rawName) return; // cancelled / empty
	const name = rawName
		.replace(/[\\/:*?"<>|]/g, "-")
		.replace(/\s+/g, " ")
		.trim();

	const notePath = `${PROJECTS_ROOT}/${name}.md`;
	if (app.vault.getAbstractFileByPath(notePath)) {
		throw new Error(`${notePath} already exists.`);
	}

	// 2. Client ---------------------------------------------------------
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
	const client = companyFile.basename;

	// 3. Contact (optional) ---------------------------------------
	const NONE = "— none —";
	const OTHER = "— type a name —";
	const people = app.vault
		.getMarkdownFiles()
		.filter((f) => f.path.startsWith(PEOPLE_ROOT))
		.filter((f) => {
			const c =
				app.metadataCache.getFileCache(f)?.frontmatter?.company ?? "";
			return c.toString().includes(client);
		})
		.sort((a, b) => a.basename.localeCompare(b.basename));

	const contactChoices = [NONE, ...people.map((f) => f.basename), OTHER];
	const pickedContact = await qa.suggester(contactChoices, contactChoices);
	if (pickedContact === undefined) return; // cancelled
	let contact = "";
	if (pickedContact === OTHER) {
		contact = ((await qa.inputPrompt("Contact name")) ?? "").trim();
	} else if (pickedContact !== NONE) {
		contact = pickedContact;
	}

	// 4. Billing model ----------------------------------------------
	const MODELS = ["hourly", "fixed", "not-to-exceed"];
	const billing_model = await qa.suggester(MODELS, MODELS);
	if (billing_model === undefined) return; // cancelled

	// 5. Quote / budget -------------------------------------------
	let quote_usd = "";
	let budget_hours = "";
	if (billing_model === "fixed" || billing_model === "not-to-exceed") {
		quote_usd = (
			(await qa.inputPrompt(
				billing_model === "fixed"
					? "Fixed price (USD) — optional"
					: "Not-to-exceed cap (USD) — optional",
			)) ?? ""
		).trim();
	}
	if (billing_model === "hourly" || billing_model === "not-to-exceed") {
		budget_hours = (
			(await qa.inputPrompt("Budget hours — optional")) ?? ""
		).trim();
	}

	// 6. Opened + scope -----------------------------------------
	const now = new Date();
	const pad = (n) => String(n).padStart(2, "0");
	const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
	const opened = (
		((await qa.inputPrompt("Opened date", "YYYY-MM-DD", today)) ?? today) ||
		today
	).trim();
	const scope = (
		(await qa.wideInputPrompt("Scope / deliverables (optional)")) ?? ""
	).trim();

	// 7. Render template --------------------------------------
	const tplFile = app.vault.getAbstractFileByPath(TEMPLATE_PATH);
	if (!tplFile) throw new Error(`Missing ${TEMPLATE_PATH}`);
	let body = await app.vault.read(tplFile);
	body = body
		.split("{{VALUE:client}}").join(client)
		.split("{{VALUE:contact}}").join(contact)
		.split("{{VALUE:billing_model}}").join(billing_model)
		.split("{{VALUE:quote_usd}}").join(quote_usd)
		.split("{{VALUE:budget_hours}}").join(budget_hours)
		.split("{{VALUE:opened}}").join(opened)
		.split("{{VALUE:scope}}").join(scope);
	if (!contact) body = body.replace('contact: "[[]]"', "contact:");
	if (!quote_usd) body = body.replace(/^quote_usd:.*\n/m, "");
	if (!budget_hours) body = body.replace(/^budget_hours:.*\n/m, "");

	// 8. Create + open --------------------------------------
	if (!app.vault.getAbstractFileByPath(PROJECTS_ROOT)) {
		await app.vault.createFolder(PROJECTS_ROOT);
	}
	const file = await app.vault.create(notePath, body);
	await app.workspace.getLeaf(false).openFile(file);
};
