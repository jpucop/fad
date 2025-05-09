import {
  IconSet,
  cleanupSVG,
  isEmptyColor,
  parseColors,
  runSVGO
} from '@iconify/tools';
import { promises as fs } from 'fs';
import path from 'path';

// Paths
const htmlFile = './index.html';
const outputDir = './dist/icons';


const mdiIconsPath = './node_modules/@iconify-json/mdi/icons.json';

// Load HTML
const html = await fs.readFile(htmlFile, 'utf8');
const matches = [...html.matchAll(/\bi-([a-z0-9]+)-([a-z0-9-]+)\b/g)];
const uniqueIcons = Array.from(new Set(matches.map(m => `${m[1]}:${m[2]}`)));
console.log(`🔍 Found ${uniqueIcons.length} icon references in source html`);

// Load MDI icon JSON
const iconSet = await importDirectory('files/svg', {
  prefix: 'test',
});

  const mdi = JSON.parse(await fs.readFile(mdiIconsPath, 'utf8'));

await fs.mkdir(outputDir, { recursive: true });

for (const iconRef of uniqueIcons) {
	const [prefix, name] = iconRef.split(':');

	if (prefix !== 'mdi') {
		console.warn(`⚠️ Unsupported prefix: ${prefix}`);
		continue;
	}

	const svg = iconSet.toSVG(name);
	if (!svg) {
		console.warn(`⚠️ Invalid icon: ${iconRef}`);
		continue;
	}

	try {
		cleanupSVG(svg);

		parseColors(svg, {
			defaultColor: 'currentColor',
			callback: (attr, colorStr, color) => {
				return !color || isEmptyColor(color) ? colorStr : 'currentColor';
			}
		});

		// ✅ returns string — do not call `.toString()` on it
		const svgString = await runSVGO(svg);

		const outputPath = path.join(outputDir, `${prefix}-${name}.svg`);
		await fs.writeFile(outputPath, svgString, 'utf8');
		console.log(`✅ Saved ${outputPath}`);
	} catch (err) {
		console.error(`❌ Failed to process ${iconRef}:`, err);
	}
}
