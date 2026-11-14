import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { UI_ASSETS } from '@/assets/uiAssets'
import { CONTACT_EMAIL } from '@/lib/contact'
import styles from './PrivacyPolicyPage.module.css'

const EFFECTIVE_DATE = 'November 8, 2026'

export function PrivacyPolicyPage() {
  useEffect(() => {
    const previous = document.title
    document.title = 'Privacy Policy · FashionRise'
    return () => {
      document.title = previous
    }
  }, [])

  return (
    <main className={styles.page} data-testid="privacy-policy-page">
      <div className={styles.inner}>
        <header className={styles.topBar}>
          <Link to="/" className={styles.brand} aria-label="FashionRise home">
            <img src={UI_ASSETS.brand.mark} alt="" className={styles.mark} draggable={false} />
            <p className={styles.wordmark}>
              Fashion<span>Rise</span>
            </p>
          </Link>
          <Link to="/login" className={styles.signIn}>
            Sign in
          </Link>
        </header>

        <h1 className={styles.title}>Privacy Policy</h1>
        <p className={styles.meta}>Effective date: {EFFECTIVE_DATE}</p>

        <p className={styles.intro}>
          This Privacy Policy explains how FashionRise (“FashionRise,” “we,” “us”) handles
          information when you use fashionrise.app, Creator Studio, FashionRise Runway, and related
          store apps. It describes FashionRise’s actual product data flows — account data, photos,
          AI features, social publishing, Stars purchases, retention, and your privacy rights.
        </p>

        <nav aria-label="Privacy policy sections">
          <ol className={styles.toc}>
            <li>
              <a href="#who-we-are">1. Who we are</a>
            </li>
            <li>
              <a href="#account">2. Account information</a>
            </li>
            <li>
              <a href="#photos">3. Uploaded photos (Create Model)</a>
            </li>
            <li>
              <a href="#studio">4. Studio designs, looks, and tech packs</a>
            </li>
            <li>
              <a href="#ai">5. AI processing</a>
            </li>
            <li>
              <a href="#runway">6. Social Runway</a>
            </li>
            <li>
              <a href="#stars">7. Stars and in-app purchases</a>
            </li>
            <li>
              <a href="#push">8. Push notifications</a>
            </li>
            <li>
              <a href="#retention">9. Data retention and deletion</a>
            </li>
            <li>
              <a href="#rights">10. Your privacy rights</a>
            </li>
            <li>
              <a href="#contact">11. Contact</a>
            </li>
          </ol>
        </nav>

        <section className={styles.section} id="who-we-are">
          <h2>1. Who we are</h2>
          <p>
            FashionRise is a fashion design studio product. You sketch garments, generate Magic
            looks and Try On previews, create personal models from photos you upload, publish looks
            to Runway if you choose, and may buy Stars for AI features.
          </p>
          <p>
            This page is public. You do not need an account to read it. Apple App Store reviewers and
            anyone visiting fashionrise.app may open{' '}
            <a href="/privacy">fashionrise.app/privacy</a>.
          </p>
        </section>

        <section className={styles.section} id="account">
          <h2>2. Account information</h2>
          <p>When you create or sign in to an account, FashionRise stores:</p>
          <ul>
            <li>Email address and username</li>
            <li>A hashed password (we do not store your password in plain text)</li>
            <li>Optional profile display name</li>
            <li>
              Session tokens: short-lived access tokens and refresh tokens (refresh tokens are stored
              hashed on the server; the browser keeps tokens in local storage for signed-in sessions)
            </li>
          </ul>
          <p>
            If you continue with Google sign-in, FashionRise receives your Google account email (and
            basic OpenID profile fields needed to create or link your FashionRise account). We do not
            keep Google access tokens as a permanent account record.
          </p>
          <p>
            Invite-based registration may also record invitation email metadata used to validate your
            invite.
          </p>
        </section>

        <section className={styles.section} id="photos">
          <h2>3. Uploaded photos (Create Model)</h2>
          <p>
            Create Model lets you upload a photo to generate a personal studio model (croquis). Those
            photos and generated model images are stored as owner-private media — they are not served
            as a public website gallery unless you later publish related looks to Runway.
          </p>
          <p>Before upload and generation, FashionRise asks you to confirm notices covering:</p>
          <ul>
            <li>Adults-only attestation for the current notice version</li>
            <li>Private storage of your photo</li>
            <li>AI processing needed to generate the model</li>
          </ul>
          <p>
            FashionRise keeps consent records (purpose, notice version, and a hash of the notice
            text) so we can show that you agreed to the then-current notices.
          </p>
        </section>

        <section className={styles.section} id="studio">
          <h2>4. Studio designs, looks, and tech packs</h2>
          <ul>
            <li>
              Sketches and saved designs are owner-private by default. Other users cannot open your
              private designs through FashionRise APIs.
            </li>
            <li>
              Magic / Try On results become items in My Looks for your account. Looks stay private
              until you publish them to Runway.
            </li>
            <li>
              Custom fabrics you upload are stored as owner-private assets for your Studio work.
            </li>
            <li>
              Create Real Design (tech packs) stores draft specifications, optional body measurement
              profiles, and generated PDF/export artifacts as owner-private files.
            </li>
          </ul>
        </section>

        <section className={styles.section} id="ai">
          <h2>5. AI processing</h2>
          <p>
            FashionRise uses AI providers to run product features. Depending on the feature and
            server configuration, that can include:
          </p>
          <ul>
            <li>
              OpenAI — for Fashion Magic illustration, Create Model image generation, Try On Person
              paths, fabric assistance, and Create Real Design AI/PDF assistance when those features
              are enabled
            </li>
            <li>
              FASHN — for certain Try On / garment virtualization paths when that provider is enabled
              and live on the server
            </li>
          </ul>
          <p>
            When you run these features, FashionRise may send the images and prompts required for that
            job (for example, a sketch capture, a Create Model photo, or a garment plate) to the
            active provider so the result can be returned to your account. Stars are deducted for
            paid AI actions according to FashionRise’s in-product pricing (for example Magic, Create
            Model, fabric, and PDF costs shown in Studio).
          </p>
          <p>
            Provider availability can change with FashionRise configuration. If a provider is not
            enabled, that path does not run.
          </p>
        </section>

        <section className={styles.section} id="runway">
          <h2>6. Social Runway</h2>
          <p>
            Runway is FashionRise’s social feed. Publishing a look makes that look visible to other
            FashionRise users according to feed rules (for example circle/friends and broader Runway
            rankings).
          </p>
          <p>Before publish, you must check a consent confirming that:</p>
          <ul>
            <li>
              You have the rights to share the design and images with other FashionRise users
            </li>
            <li>You grant FashionRise permission to display that content on the Runway</li>
          </ul>
          <p>
            FashionRise records that Runway share consent. Published cards can show your look image,
            title, and username. Other users may like, score, and comment. You can remove a look from
            Runway (unpublish), which deletes that public gallery listing.
          </p>
          <p>
            Friend connections use FashionRise usernames so you can build a private circle feed of
            friends’ published looks.
          </p>
        </section>

        <section className={styles.section} id="stars">
          <h2>7. Stars and in-app purchases</h2>
          <p>
            Stars are FashionRise’s in-product balance used for AI features. Your Stars balance is
            stored on your account.
          </p>
          <p>
            When you buy Stars through Apple or Google in-app purchase (store builds), FashionRise
            records a purchase confirmation needed to credit Stars safely — including platform,
            product id, store transaction id, and Stars credited — so the same store transaction is
            not credited twice. Payment card details are handled by Apple or Google, not entered into
            FashionRise’s own checkout form for those store purchases.
          </p>
        </section>

        <section className={styles.section} id="push">
          <h2>8. Push notifications</h2>
          <p>
            If you allow browser or device push for Runway activity, FashionRise stores a push
            subscription (endpoint and encryption keys, plus optional user-agent metadata) so we can
            deliver notices such as likes, scores, and comments on your published looks. You can turn
            push off in the product where that control is offered.
          </p>
        </section>

        <section className={styles.section} id="retention">
          <h2>9. Data retention and deletion</h2>
          <ul>
            <li>
              Create Model source photos are subject to FashionRise retention rules for abandoned
              uploads, maximum source age, and post-accept cleanup of source bytes (configured server
              retention windows; cleanup is applied by FashionRise’s media maintenance process).
            </li>
            <li>
              Removing a look from My Looks marks it deleted for your gallery view. That action does
              not by itself erase underlying AI job image files on disk.
            </li>
            <li>
              Unpublishing from Runway removes the public Runway listing for that look.
            </li>
            <li>
              Signing out revokes refresh tokens for that session path. Local browser storage may
              still hold client preferences until cleared.
            </li>
          </ul>
          <p>
            You can permanently delete your FashionRise account from inside the app or website: open{' '}
            <strong>My Studio</strong> → <strong>Delete account</strong>, then type DELETE to confirm.
            That removes your account profile and associated designs, looks, and private media FashionRise
            can delete. If you need additional help after deletion, contact us using the email below.
          </p>
        </section>

        <section className={styles.section} id="rights">
          <h2>10. Your privacy rights</h2>
          <p>Depending on where you live, you may have rights to:</p>
          <ul>
            <li>Access personal information FashionRise holds about your account</li>
            <li>Correct inaccurate account details (such as username/email where supported)</li>
            <li>Delete your account in-app (My Studio → Delete account) or request further deletion help</li>
            <li>Object to certain processing, including optional Runway publishing and push</li>
            <li>Withdraw consents that are based on consent (for example Runway publish consent for
              future publishes, Create Model notices for future uploads, or push permission)</li>
          </ul>
          <p>
            FashionRise does not sell your personal information. We do not use advertising analytics
            SDKs in the FashionRise web app. Core third parties that may process data for product
            features are identity (Google sign-in, when used), AI providers (when a feature is live),
            app stores for Stars purchases, and push delivery services when notifications are enabled.
          </p>
        </section>

        <section className={styles.section} id="contact">
          <h2>11. Contact</h2>
          <p>
            Privacy questions or requests:{' '}
            <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
          </p>
          <p>
            You can also use <strong>My Studio → Contact us</strong> after signing in. Messages sent
            that way open your email app to {CONTACT_EMAIL}.
          </p>
        </section>

        <p className={styles.footerNote}>
          FashionRise may update this Privacy Policy as the product changes. The effective date above
          shows the current version. Continued use of FashionRise after an update means the revised
          policy applies to new activity from that date forward.
        </p>
      </div>
    </main>
  )
}
