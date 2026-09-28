using UnityEngine;

namespace MathGame.Player
{
    [RequireComponent(typeof(Rigidbody2D))]
    public class PlayerController : MonoBehaviour
    {
        [SerializeField, Min(0.1f)] float moveSpeed = 4f;
        [SerializeField, Min(0.1f)] float acceleration = 48f;

        Rigidbody2D _body;
        Animator _animator;
        Vector2 _facing = Vector2.down;
        bool _wasHorizontal;
        bool _wasVertical;
        bool _useHorizontal = true;

        static readonly int MoveXHash = Animator.StringToHash("MoveX");
        static readonly int MoveYHash = Animator.StringToHash("MoveY");
        static readonly int SpeedHash = Animator.StringToHash("Speed");
        static readonly int IsMovingHash = Animator.StringToHash("IsMoving");

        int _movementLocks;

        public Vector2 Facing => _facing;
        public bool MovementLocked => _movementLocks > 0;

        public void PushMovementLock()
        {
            _movementLocks++;
        }

        public void PopMovementLock()
        {
            if (_movementLocks > 0)
                _movementLocks--;
        }

        void Awake()
        {
            _body = GetComponent<Rigidbody2D>();
            _animator = GetComponent<Animator>();
            _body.gravityScale = 0f;
            _body.freezeRotation = true;
        }

        void Update()
        {
            UpdateAnimator();
        }

        void FixedUpdate()
        {
            if (MovementLocked)
            {
                _body.linearVelocity = Vector2.zero;
                return;
            }

            Vector2 input = ReadCardinalInput();
            if (input.sqrMagnitude > 0f)
                _facing = input;

            Vector2 targetVelocity = input * moveSpeed;
            _body.linearVelocity = Vector2.MoveTowards(
                _body.linearVelocity,
                targetVelocity,
                acceleration * Time.fixedDeltaTime);
        }

        // Newest axis wins so diagonals snap to a single cardinal direction.
        Vector2 ReadCardinalInput()
        {
            float x = 0f;
            float y = 0f;
            if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow))
                x -= 1f;
            if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow))
                x += 1f;
            if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow))
                y -= 1f;
            if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow))
                y += 1f;

            bool horizontal = x != 0f;
            bool vertical = y != 0f;
            if (horizontal && vertical)
            {
                bool horizontalNew = !_wasHorizontal;
                bool verticalNew = !_wasVertical;
                if (verticalNew && !horizontalNew)
                    _useHorizontal = false;
                else if (horizontalNew && !verticalNew)
                    _useHorizontal = true;

                if (_useHorizontal)
                    y = 0f;
                else
                    x = 0f;
            }
            else if (horizontal)
            {
                _useHorizontal = true;
            }
            else if (vertical)
            {
                _useHorizontal = false;
            }

            _wasHorizontal = horizontal;
            _wasVertical = vertical;
            return new Vector2(x, y);
        }

        void UpdateAnimator()
        {
            if (_animator == null || _animator.runtimeAnimatorController == null)
                return;

            Vector2 velocity = _body.linearVelocity;
            bool moving = !MovementLocked && velocity.sqrMagnitude > 0.05f;
            _animator.SetFloat(MoveXHash, _facing.x);
            _animator.SetFloat(MoveYHash, _facing.y);
            _animator.SetFloat(SpeedHash, velocity.magnitude);
            _animator.SetBool(IsMovingHash, moving);
        }

    }
}
