def configure(parser):
    parser.add_argument(
        "--operators",
        help="Path to the operators configuration file",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Disable operators modifications",
    )
    args, _ = parser.parse_known_args()
    return args
