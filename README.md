![logo](./assets/logo.svg)

![Stars](https://img.shields.io/github/stars/fabifont/getarch?style=social)

![Pre-commit checks](https://github.com/fabifont/getarch/actions/workflows/pre-commit.yaml/badge.svg) ![Build and release executable](https://github.com/fabifont/getarch/actions/workflows/build-and-release.yaml/badge.svg) ![Test getarch](https://github.com/fabifont/getarch/actions/workflows/test-getarch.yaml/badge.svg)

![Open issues](https://img.shields.io/github/issues/fabifont/getarch?color=9cf) ![Open pull requests](https://img.shields.io/github/issues-pr/fabifont/getarch?color=9cf)

![License](https://img.shields.io/github/license/fabifont/getarch?color=blue) ![Latest release](https://img.shields.io/github/v/release/fabifont/getarch)

# getarch

**getarch** is an automated tool designed to streamline the installation process of Arch Linux. Written purely in Python and relying solely on the standard library, **getarch** is simple, lightweight, and user-friendly. It aims to provide a faster alternative to the traditional Arch Linux installation process.

Although **getarch** simplifies the installation process, it is not designed for Arch Linux beginners. Before using **getarch**, it's important to understand the basics of Arch Linux and the Linux system administration. I highly recommend that new users first manually install Arch Linux by following the [official Arch Linux installation guide](https://wiki.archlinux.org/index.php/installation_guide) to familiarize themselves with the system. This tool is most useful for users who are already familiar with Arch Linux but want to save time on the installation process.

## Current limitations and future plans

At present, **getarch** operates through a configuration file only and supports only btrfs and ext4 filesystem and a fixed partition scheme. However, I have plans to enhance its functionality:

* Support for additional filesystems and partition schemes will be added.
* An option for fully custom partitioning is planned.
* Integrate a Text-based User Interface (TUI) based on `curses` from Python's standard library to improve user interaction and flexibility.

## Installation

Users should download the latest release of the **getarch** executable from the GitHub releases page. The following command can be used to fetch the latest release:

```bash
curl -LJO https://github.com/fabifont/getarch/releases/latest/download/getarch
chmod +x getarch
```

## Usage

Once you have the **getarch** executable, you can run it with the following options:

* `-v`, `--version`: Show the version of the **getarch** tool and exit.
* `-c`, `--config`: Path to the configuration file. This is a JSON file that contains your desired system configuration. An example of this file can be found in `example/config.json`.
* `-pv`, `--possible-values`: This option can take one of the following arguments: `disks`, `locales`, `langs`, `keymaps`, `timezones`. This will return the possible values for the respective configuration option.
* `-t`, `--test`: exit before rebooting to perform tests

For example, to get a list of possible locales, you would use:

```bash
./getarch --possible-values locales
```

Create a `config.json` file that fits your installation needs (see `example/config.json` for reference) and run the tool on your Arch Linux live environment:

```bash
./getarch -c path_to_your_config.json
```

The tool will then install Arch Linux according to your provided configuration.

## Developing

For developers interested in contributing to **getarch**, clone the repository using the following command:

```bash
git clone https://github.com/fabifont/getarch.git
cd getarch
```

After cloning the repository, you can install the development dependencies:

```bash
poetry install
```

This project uses pre-commit, flake8, black, and pyright to ensure code quality and consistency. After cloning the project and installing dependencies, set up the pre-commit hooks by running:

```bash
pre-commit install
```

The pre-commit configuration includes checks for trailing whitespace, syntax (AST), docstrings, JSON, merge conflicts, debug statements, file endings, large files, case conflicts, TOML, YAML, Python imports (isort), Python formatting (Black), Python linting (flake8), security (Bandit), and type checking (Pyright).

These hooks will automatically be run on every commit. If a hook finds an issue that it can't automatically resolve, the commit will be aborted, and you'll be given a description of what went wrong.

If you want to run pre-commit manually without committing, for example, to check if your code will pass before committing, you can use the following command:

```bash
pre-commit run --all-files
```

Contributors are required to adhere to these checks. All code submitted through merge requests must pass all CI workflows. GitHub workflows are set up to automatically verify this. Merge requests with failing checks will not be accepted.

For testing purposes, a `test_resources` directory contains some bash scripts to create and run a QEMU-KVM virtual machine. Before running these scripts, make sure to place an Arch Linux ISO renamed to `arch.iso` in the same directory. The virtual machine will use the parent directory of the scripts as a shared folder, available after boot using the following mount command:

```bash
mount -t virtiofs shared_folder /mnt
```

**getarch** follows the [Semantic Versioning 2.0.0](https://semver.org/) standard. This means that version numbers and the way they change convey meaning about the underlying changes in a release.

## Contributing

Contributions to **getarch** are very welcome! Whether it involves reporting issues, improving the documentation, or enhancing the code, every contribution is valuable.

## License

This project is licensed under the GPL-3.0 license. See `LICENSE` for more details.

## Disclaimer

**getarch** is provided "as is", without warranty of any kind, express or implied. Use it at your own risk. The actions performed by this tool are potentially destructive, so it's important to back up your data before using it.
