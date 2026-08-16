# Ubuntu Install Instruction

On an Ubuntu desktop, open a terminal (either search for the terminal application or use the shortcut ctrl+alt+t). 


First install `curl`, which lets you download files using commands.

```bash
sudo apt update
sudo apt install curl
```


We are going to use curl to install `uv`, which is currently (as of 2025-09-23)
the easiest way to install a local copy of Python that doesn't interfere with
system libraries. 


```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

We will use `uv` to create a virtual environment (venv), which is the mechanism
that prevents aforementioned system interference.  NOTE: you will have to
"activate" this venv to use the program. The following instructions will make
this more clear. 


```bash
# To let your current terminal know where the "uv" command is, we use the
# following command.
source $HOME/.local/bin/env

# We now use uv to create the virtual environment
uv venv --seed --python "python3.11" ibeis_venv
```

We now "activate" the venv

```bash
source ibeis_venv/bin/activate
```

Your terminal will now prefix new lines with "(ibeis_venv)", which indicates
you have activated the virtual environment successfully, from here on, all
python processes happen in this context, so it is easy to start fresh if you
run into dependency issues.


Now that we have a Python environment, we can install ibeis

```bash
uv pip install ibeis[headless]
```


Now you should be able to run the `ibeis` command, which opens the GUI.

```bash
ibeis
```


# Starting IBEIS after it is installed.

Once you install ibeis, if you reboot your machine, you will likely want to
reopen it. To do this, open a terminal and run:

```bash
source ibeis_venv/bin/activate
```

And then start ibeis.

```bash
ibeis
```

# Bonus: Make the venv default to start faster.

NOTE: You can have the virtual environment activation happen automatically when
you open a terminal if you add the `source ibeis_venv/bin/activate` command to
your `.bashrc` file (which lives in your home directory). A command that will
add this line to the end of your .bashrc is:

```bash
echo "source ibeis_venv/bin/activate" >> ~/.bashrc
```

Now when you open a new terminal, all you need to do is enter the command: `ibeis`.
