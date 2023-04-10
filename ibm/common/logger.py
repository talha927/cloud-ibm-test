class Logger:
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    green = "\x1b[32;20m"
    cyan = "\x1b[36;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    def info(self, msg):
        """Logs a message with 'GREY' color."""
        formatted_msg = self.grey + str(msg) + self.reset
        print(formatted_msg)

    def debug(self, msg):
        """Logs a message with 'GREY' color."""
        formatted_msg = self.grey + str(msg) + self.reset
        print(formatted_msg)

    def fail(self, msg):
        """Logs a message with 'RED' color.
        Intended to be used by resources being failed to create/delete/update.
        """
        formatted_msg = self.red + str(msg) + self.reset
        print(formatted_msg)

    def error(self, msg):
        """Logs a message with 'RED' color.
        Intended for error message.
        """
        formatted_msg = self.red + str(msg) + self.reset
        print(formatted_msg)

    def success(self, msg):
        """Logs a message with 'GREEN' color."""
        formatted_msg = self.green + str(msg) + self.reset
        print(formatted_msg)

    def note(self, msg):
        """Logs a message with 'CYAN' color."""
        formatted_msg = self.cyan + str(msg) + self.reset
        print(formatted_msg)


def get_logger():
    return Logger()
