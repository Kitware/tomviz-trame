def configure(parser):
    parser.add_argument(
        "--catalog",
        "--operators",  # former name, kept so existing launch scripts work
        dest="catalog",
        help="Path to the catalog configuration file (scanned directories and "
        "modules, favorites); default: ~/.tomviz/catalog.json",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Never write the catalog configuration (favorites)",
    )
    args, _ = parser.parse_known_args()
    return args
