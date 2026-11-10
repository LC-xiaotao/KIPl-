/**
 * KiPI Power Integrity — EasyEDA Pro (嘉立创EDA专业版) extension.
 *
 * KiPI (https://github.com/drewsum/KiPI) is a desktop power-integrity analyzer.
 * EasyEDA Pro has no in-process plugin API for Python/Qt, so this extension
 * hands the board over as ODB++: EasyEDA Pro's own exporter writes the copper,
 * nets, pads, vias and stackup, and KiPI's ODB++ reader opens the result.
 *
 * The menu is registered in extension.json (headerMenus.pcb); the exported
 * functions below are looked up by name through `registerFn`.
 */

// EDMT_EditorDocumentType.PCB. Kept as a number because the enum objects are
// not exposed to every extension context.
const DOCUMENT_TYPE_PCB = 3;

function t(tag: string): string {
	return eda.sys_I18n.text(tag);
}

/** A file name that every file system accepts, without the extension. */
function safeBaseName(name: string | undefined | null): string {
	const cleaned = (name ?? "")
		.replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_")
		.replace(/\s+/g, "_")
		.replace(/^[._]+|[._]+$/g, "")
		.slice(0, 80);
	return cleaned || "board";
}

async function activePcbName(): Promise<string | null> {
	const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
	if (!doc || doc.documentType !== DOCUMENT_TYPE_PCB) {
		return null;
	}
	const project = await eda.dmt_Project.getCurrentProjectInfo();
	return safeBaseName(project?.friendlyName ?? project?.name ?? doc.uuid);
}

/** Called once when the extension loads. */
export function activate(): void {
	// Nothing to set up: the menu actions are registered from extension.json.
}

/**
 * Export the active PCB as ODB++ and save it where the user chooses.
 * The ODB++ job carries the copper features, nets, pads, vias and stackup
 * that KiPI needs; open the saved .tgz in KiPI afterwards.
 */
export async function exportToKipi(): Promise<void> {
	const base = await activePcbName();
	if (base === null) {
		eda.sys_Dialog.showInformationMessage(t("export.needPcb"), "KiPI");
		return;
	}

	eda.sys_Message.showToastMessage(t("export.running"));
	try {
		const file = await eda.pcb_ManufactureData.getOpenDatabaseDoublePlusFile(
			`${base}_KiPI`,
			"mm",
		);
		if (!file) {
			throw new Error(t("export.noFile"));
		}
		await eda.sys_FileSystem.saveFile(file, `${base}_KiPI.tgz`);
		eda.sys_Dialog.showInformationMessage(t("export.done"), "KiPI");
	}
	catch (error) {
		const reason = error instanceof Error ? error.message : String(error);
		eda.sys_Dialog.showInformationMessage(
			`${t("export.failed")}\n\n${reason}`,
			"KiPI",
		);
	}
}

/** What the extension does and how to finish the workflow in KiPI. */
export function showHelp(): void {
	eda.sys_Dialog.showInformationMessage(t("help.body"), "KiPI");
}
