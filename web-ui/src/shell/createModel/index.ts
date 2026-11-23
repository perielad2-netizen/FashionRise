/**
 * Canonical Create Model surface.
 *
 * Both product entry points mount the same wizard component and hit the same
 * personal-croquis API / moderation / Stars pipeline. The only allowed
 * difference is post-accept navigation (gallery stay vs Studio pin).
 */
export {
  CreateMyCroquisWizard as CreateModelWizard,
  CreateMyCroquisWizard,
  type CreateMyCroquisWizardProps,
  type CreateModelEntryPoint,
} from '@/shell/components/CreateMyCroquisWizard'
