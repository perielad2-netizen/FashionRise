import { CreatorWorkspace } from '@/design-lab/components/CreatorWorkspace'
import { FashionRiseAppShell } from '@/design-lab/components/FashionRiseAppShell'
import '@/design-lab/designLabTokens.css'
import styles from './DesignStudioLabPage.module.css'

/**
 * DEV-only visual reconstruction of the approved Creator Studio mockup.
 * Not authenticated. Not production Studio. Prototype controls do not call APIs.
 */
export function DesignStudioLabPage() {
  return (
    <div className={`designLabRoot ${styles.page}`}>
      <div className={styles.banner}>Development prototype · /_design/studio</div>
      <div className={styles.shellPad}>
        <FashionRiseAppShell>
          <CreatorWorkspace />
        </FashionRiseAppShell>
      </div>
    </div>
  )
}
