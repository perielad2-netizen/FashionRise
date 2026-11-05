import { UI_ASSETS } from '@/assets/uiAssets'

/** Design-lab only model grid. Real selectable production assets are marked. */
export type DesignLabModelCard = {
  id: string
  label: string
  src: string
  filter: 'female' | 'male'
  /** Production-backed vs visual placeholder for the mock grid density. */
  kind: 'production' | 'placeholder'
}

export const DESIGN_LAB_MODELS: DesignLabModelCard[] = [
  {
    id: 'prod-female',
    label: 'Female',
    src: UI_ASSETS.model.female,
    filter: 'female',
    kind: 'production',
  },
  {
    id: 'prod-male',
    label: 'Male',
    src: UI_ASSETS.model.male,
    filter: 'male',
    kind: 'production',
  },
  {
    id: 'ph-f1',
    label: 'Pose A',
    src: '/assets/ui/design-lab/models/croquis-female-01.png',
    filter: 'female',
    kind: 'placeholder',
  },
  {
    id: 'ph-f2',
    label: 'Pose B',
    src: '/assets/ui/design-lab/models/croquis-female-02.png',
    filter: 'female',
    kind: 'placeholder',
  },
  {
    id: 'ph-f3',
    label: 'Pose C',
    src: '/assets/ui/design-lab/models/croquis-female-03.png',
    filter: 'female',
    kind: 'placeholder',
  },
  {
    id: 'ph-f4',
    label: 'Pose D',
    src: '/assets/ui/design-lab/models/croquis-female-04.png',
    filter: 'female',
    kind: 'placeholder',
  },
  {
    id: 'ph-m1',
    label: 'Pose E',
    src: '/assets/ui/design-lab/models/croquis-male-01.png',
    filter: 'male',
    kind: 'placeholder',
  },
  {
    id: 'ph-m2',
    label: 'Pose F',
    src: '/assets/ui/design-lab/models/croquis-male-02.png',
    filter: 'male',
    kind: 'placeholder',
  },
]

export const DESIGN_LAB_CANVAS_CROQUIS = UI_ASSETS.canvas.female
export const DESIGN_LAB_BRAND_MARK = UI_ASSETS.brand.mark
export const DESIGN_LAB_BRAND_LOGO = UI_ASSETS.brand.logo
