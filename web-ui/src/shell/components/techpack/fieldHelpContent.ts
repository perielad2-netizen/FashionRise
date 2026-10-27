export type FieldHelpDiagram =
  | 'silhouette'
  | 'inseam'
  | 'rise'
  | 'shoulder'
  | 'sleeve'
  | 'length'
  | null

export type FieldHelpEntry = {
  title: string
  explanation: string
  examples?: string[]
  diagram?: FieldHelpDiagram
}

export const SHELL_SUGGESTIONS = [
  'cotton',
  'denim',
  'linen',
  'silk',
  'polyester blend',
  'jersey knit',
  'wool blend',
  'other',
  'unknown',
] as const

export const CLOSURE_SUGGESTIONS = [
  'buttons',
  'zipper',
  'invisible zipper',
  'snaps',
  'hook-and-eye',
  'elastic waistband',
  'pull-on',
  'none',
] as const

export const SILHOUETTE_SUGGESTIONS = [
  'slim',
  'regular',
  'relaxed',
  'oversized',
  'fitted',
  'A-line',
  'flared',
  'straight',
  'tapered',
  'wide-leg',
] as const

export const FIT_PREFERENCES = [
  'slim',
  'fitted',
  'regular',
  'relaxed',
  'oversized',
] as const

export const PIECE_CATEGORIES = [
  'dress',
  'shirt',
  'top',
  'jacket',
  'skirt',
  'trousers',
  'shorts',
  'jumpsuit',
  'set',
  'other',
] as const

export const FIELD_HELP: Record<string, FieldHelpEntry> = {
  shell_fabric: {
    title: 'Shell fabric',
    explanation:
      'The main outer fabric of the garment — what the customer sees and feels first. Note fiber family or a known mill name if you have one.',
    examples: ['cotton twill', 'denim 12oz', 'silk charmeuse', 'jersey knit', 'unknown'],
  },
  composition: {
    title: 'Composition',
    explanation:
      'Fiber blend percentages for the shell (and lining if critical). Factories need this for washing, shrinkage, and sourcing.',
    examples: ['100% cotton', '98% cotton / 2% elastane', '70% wool / 30% polyester'],
  },
  closure: {
    title: 'Closure',
    explanation:
      'How the garment opens and closes — zipper type, buttons, snaps, elastic, or pull-on with no hardware.',
    examples: ['invisible zipper', 'button placket', 'elastic waistband', 'pull-on'],
  },
  silhouette: {
    title: 'Silhouette',
    explanation:
      'Overall shape relative to the body: slim, regular, relaxed, A-line, tapered, wide-leg, and similar fit language.',
    examples: ['slim', 'regular', 'A-line', 'wide-leg'],
    diagram: 'silhouette',
  },
  height: {
    title: 'Height',
    explanation: 'Full body height from crown to floor. Used once for the sample model — not a garment POM.',
    examples: ['165 cm', '5 ft 5 in'],
  },
  bust: {
    title: 'Bust / chest (body)',
    explanation: 'Body circumference at the fullest bust/chest point. Separate from finished garment chest.',
    examples: ['86 cm'],
  },
  waist: {
    title: 'Waist (body)',
    explanation: 'Natural body waist circumference. Do not confuse with finished waistband POM.',
    examples: ['68 cm'],
  },
  hip: {
    title: 'Hip (body)',
    explanation: 'Body circumference at the fullest hip. Separate from finished hip circumference.',
    examples: ['94 cm'],
  },
  body_inseam: {
    title: 'Inseam (body)',
    explanation: 'Inside leg length from crotch to floor (or preferred hem). Helps relate trousers/shorts length.',
    examples: ['78 cm'],
    diagram: 'inseam',
  },
  chest_bust: {
    title: 'Chest / bust (finished)',
    explanation: 'Finished garment circumference at chest/bust. Usually larger than body bust by ease.',
    examples: ['body 86 + 4 cm ease → 90 cm'],
  },
  shoulder_width: {
    title: 'Shoulder width',
    explanation: 'Point-to-point across the shoulders on the finished garment (seam to seam).',
    examples: ['38 cm'],
    diagram: 'shoulder',
  },
  garment_length: {
    title: 'Garment length',
    explanation: 'Typically high-point shoulder (HPS) to hem for tops/dresses, or equivalent center-back length.',
    examples: ['HPS to hem 110 cm'],
    diagram: 'length',
  },
  sleeve_length: {
    title: 'Sleeve length',
    explanation: 'Shoulder seam (or armhole crown) to cuff edge along the outer sleeve.',
    examples: ['58 cm'],
    diagram: 'sleeve',
  },
  armhole: {
    title: 'Armhole',
    explanation: 'Armhole circumference of the finished garment — affects mobility and sleeve set.',
    examples: ['42 cm'],
  },
  cuff: {
    title: 'Cuff opening',
    explanation: 'Finished opening at the sleeve end (circumference or flat width × 2).',
    examples: ['22 cm circumference'],
  },
  hem: {
    title: 'Hem circumference',
    explanation: 'Finished hem opening circumference for tops, dresses, jackets, or skirts.',
    examples: ['110 cm'],
  },
  neckline: {
    title: 'Neckline / collar',
    explanation: 'Neck opening circumference or collar stand measurement as appropriate for the style.',
    examples: ['40 cm neck opening'],
  },
  finished_waist: {
    title: 'Waist (finished)',
    explanation: 'Finished waistband or waist seam circumference on the garment.',
    examples: ['72 cm'],
  },
  finished_hip: {
    title: 'Hip (finished)',
    explanation: 'Finished garment circumference at hip level.',
    examples: ['98 cm'],
  },
  inseam: {
    title: 'Inseam (finished)',
    explanation: 'Crotch seam to hem along the inside leg of trousers or shorts.',
    examples: ['76 cm'],
    diagram: 'inseam',
  },
  outseam: {
    title: 'Outseam',
    explanation: 'Waistband top to hem along the outer side seam.',
    examples: ['100 cm'],
  },
  front_rise: {
    title: 'Front rise',
    explanation: 'Center-front waistband top to crotch seam intersection.',
    examples: ['26 cm'],
    diagram: 'rise',
  },
  back_rise: {
    title: 'Back rise',
    explanation: 'Center-back waistband top to crotch seam intersection.',
    examples: ['34 cm'],
    diagram: 'rise',
  },
  thigh: {
    title: 'Thigh',
    explanation: 'Finished thigh circumference at the fullest part of the leg (usually 2–3 cm below crotch).',
    examples: ['58 cm'],
  },
  knee: {
    title: 'Knee',
    explanation: 'Finished circumference at knee level.',
    examples: ['42 cm'],
  },
  leg_opening: {
    title: 'Leg opening',
    explanation: 'Finished hem opening circumference of each leg.',
    examples: ['36 cm'],
  },
  waistband: {
    title: 'Waistband height',
    explanation: 'Finished height of the waistband (not circumference).',
    examples: ['3.5 cm'],
  },
  skirt_length: {
    title: 'Skirt length',
    explanation: 'Waistband top (or natural waist) to hem.',
    examples: ['60 cm'],
    diagram: 'length',
  },
  opening: {
    title: 'Opening / slit',
    explanation: 'Slit, vent, or placket opening length when relevant to the style.',
    examples: ['18 cm side slit'],
  },
}

/** Map finished POM keys → FieldHelp dictionary id. */
export const POM_HELP_KEY: Record<string, string> = {
  chest_bust: 'chest_bust',
  shoulder_width: 'shoulder_width',
  garment_length: 'garment_length',
  sleeve_length: 'sleeve_length',
  armhole: 'armhole',
  cuff: 'cuff',
  hem: 'hem',
  neckline: 'neckline',
  waist: 'finished_waist',
  hip: 'finished_hip',
  inseam: 'inseam',
  outseam: 'outseam',
  front_rise: 'front_rise',
  back_rise: 'back_rise',
  thigh: 'thigh',
  knee: 'knee',
  leg_opening: 'leg_opening',
  waistband: 'waistband',
  skirt_length: 'skirt_length',
  opening: 'opening',
}

export const POM_LABELS: Record<string, string> = {
  chest_bust: 'Chest / bust',
  shoulder_width: 'Shoulder width',
  garment_length: 'Garment length',
  sleeve_length: 'Sleeve length',
  armhole: 'Armhole',
  cuff: 'Cuff',
  hem: 'Hem',
  neckline: 'Neckline / collar',
  waist: 'Waist',
  hip: 'Hip',
  inseam: 'Inseam',
  outseam: 'Outseam',
  front_rise: 'Front rise',
  back_rise: 'Back rise',
  thigh: 'Thigh',
  knee: 'Knee',
  leg_opening: 'Leg opening',
  waistband: 'Waistband height',
  skirt_length: 'Skirt length',
  opening: 'Opening / slit',
}

export const FINISHED_POM_BY_CATEGORY: Record<string, readonly string[]> = {
  shirt: [
    'chest_bust',
    'shoulder_width',
    'garment_length',
    'sleeve_length',
    'armhole',
    'cuff',
    'hem',
    'neckline',
  ],
  top: ['chest_bust', 'shoulder_width', 'garment_length', 'sleeve_length', 'armhole', 'hem', 'neckline'],
  jacket: [
    'chest_bust',
    'shoulder_width',
    'garment_length',
    'sleeve_length',
    'armhole',
    'hem',
    'neckline',
  ],
  trousers: [
    'waist',
    'hip',
    'inseam',
    'outseam',
    'front_rise',
    'back_rise',
    'thigh',
    'knee',
    'leg_opening',
    'waistband',
  ],
  shorts: ['waist', 'hip', 'inseam', 'outseam', 'front_rise', 'back_rise', 'thigh', 'leg_opening', 'waistband'],
  skirt: ['waist', 'hip', 'skirt_length', 'waistband', 'hem', 'opening'],
  dress: [
    'chest_bust',
    'waist',
    'hip',
    'garment_length',
    'shoulder_width',
    'armhole',
    'sleeve_length',
    'hem',
    'neckline',
  ],
  jumpsuit: [
    'chest_bust',
    'waist',
    'hip',
    'garment_length',
    'inseam',
    'shoulder_width',
    'sleeve_length',
    'hem',
  ],
  other: ['garment_length', 'waist', 'hip', 'chest_bust'],
  set: [],
}

export function getFieldHelp(key: string): FieldHelpEntry {
  return (
    FIELD_HELP[key] ?? {
      title: key.replace(/_/g, ' '),
      explanation: 'Designer-entered technical detail for this tech pack.',
    }
  )
}
